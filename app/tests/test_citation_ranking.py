"""Deterministic RRF fusion, identity-only merge, and related groups."""

from skills.citation.providers.base import ProviderRecord
from skills.citation.ranking import (
    RRF_K,
    fuse_ranked_lists,
    representative_candidates,
)


def _rec(provider, rank, *, doi=None, title="", pid=None, year=None,
         authors=None, venue="", work_type="", score=None, identifiers=None):
    return ProviderRecord(
        provider=provider,
        provider_id=pid or f"{provider}:{doi or title or rank}",
        rank=rank,
        title=title,
        authors=list(authors or []),
        year=year,
        venue=venue,
        doi=doi,
        work_type=work_type,
        raw_score=score,
        identifiers=dict(identifiers or {}),
    )


def test_rrf_accumulates_across_providers_with_fixed_k():
    crossref = [
        _rec("crossref", 0, doi="10.1234/a", title="Paper A"),
        _rec("crossref", 1, doi="10.1234/b", title="Paper B"),
    ]
    openalex = [
        _rec("openalex", 0, doi="10.1234/b", title="Paper B"),
        _rec("openalex", 1, doi="10.1234/a", title="Paper A"),
    ]
    candidates = fuse_ranked_lists(
        [crossref, openalex], query="papers", workflow_id="w1"
    )
    # Both works appear in both lists; sums are equal (1/61+1/62 each), so
    # the deterministic tie-break (merge key: doi:10.1234/a < doi:10.1234/b)
    # decides the order.
    assert [c.doi for c in candidates] == ["10.1234/a", "10.1234/b"]
    assert RRF_K == 60


def test_raw_scores_are_kept_but_do_not_drive_order():
    # crossref score 99 vs openalex score 0.1 must not matter; only ranks do.
    crossref = [_rec("crossref", 0, doi="10.1/x" + "0" * 3, title="X", score=99.0)]
    openalex = [
        _rec("openalex", 0, doi="10.2222/top", title="Top", score=0.1),
        _rec("openalex", 1, doi="10.1000/x", title="X", score=0.05),
    ]
    candidates = fuse_ranked_lists([crossref, openalex], query="q", workflow_id="w")
    # Both rank-0 hits tie on RRF; deterministic tie-break resolves, and the
    # openalex rank-1 hit is strictly below any rank-0 hit.
    assert candidates[-1].doi == "10.1000/x"


def test_merge_only_on_same_doi_or_same_provider_id():
    lists = [
        [_rec("crossref", 0, doi="10.1234/same", title="Work v2", year=2021)],
        [_rec("openalex", 0, doi="10.1234/same", title="Work v2", year=2021)],
        # Same title but different DOI: must stay separate.
        [_rec("openalex", 1, doi="10.1234/preprint", title="Work v2", year=2020)],
    ]
    candidates = fuse_ranked_lists(lists, query="work", workflow_id="w")
    dois = sorted(c.doi for c in candidates)
    assert dois == ["10.1234/preprint", "10.1234/same"]
    merged = next(c for c in candidates if c.doi == "10.1234/same")
    assert set(merged.provider_ids) == {"crossref", "openalex"}
    assert merged.provider_ranks == {"crossref": 0, "openalex": 0}


def test_doi_less_lookalike_joins_related_group_not_merged():
    lists = [
        [_rec("crossref", 0, doi="10.1234/published", title="Same Title",
              year=2021, authors=["Ada Lovelace"])],
        [_rec("web", 0, title="Same Title", year=2021,
              authors=["Ada Lovelace"], pid="web:https://example.org/p")],
    ]
    candidates = fuse_ranked_lists(lists, query="same title", workflow_id="w")
    assert len(candidates) == 2  # never destructively merged
    groups = {c.related_group for c in candidates}
    assert len(groups) == 1 and None not in groups


def test_distinct_doi_versions_fold_but_remain_independently_addressable():
    candidates = fuse_ranked_lists(
        [
            [_rec(
                "openalex", 0, doi="10.1234/preprint", title="Same Work",
                year=2024, authors=["Ada Lovelace"], venue="arXiv",
                work_type="preprint",
            )],
            [_rec(
                "crossref", 0, doi="10.1234/published", title="Same Work",
                year=2025, authors=["Ada Lovelace"], venue="FPGA",
                work_type="proceedings-article",
            )],
        ],
        query="same work",
        workflow_id="w",
    )

    assert {candidate.doi for candidate in candidates} == {
        "10.1234/preprint", "10.1234/published",
    }
    assert len({candidate.related_group for candidate in candidates}) == 1
    [visible] = representative_candidates(candidates)
    assert visible.doi == "10.1234/published"
    assert visible.related_candidate_ids


def test_similar_title_with_different_authors_does_not_group():
    candidates = fuse_ranked_lists(
        [
            [_rec(
                "crossref", 0, doi="10.1234/a", title="Fast AI Inference",
                year=2025, authors=["Ada Lovelace"],
            )],
            [_rec(
                "openalex", 0, doi="10.1234/b", title="Fast AI Inference",
                year=2025, authors=["Grace Hopper"],
            )],
        ],
        query="AI inference",
        workflow_id="w",
    )

    assert all(candidate.related_group is None for candidate in candidates)
    assert len(representative_candidates(candidates)) == 2


def test_lexical_mode_downranks_query_title_parody_without_hard_filtering():
    ranked = [[
        _rec(
            "crossref", 0, doi="10.1234/noise",
            title="Inference in Partially Observable Decision Processes",
        ),
        _rec(
            "crossref", 1, doi="10.1234/relevant",
            title="Hardware Acceleration for Efficient AI Inference",
        ),
    ]]

    rrf = fuse_ranked_lists(
        ranked, query="AI inference acceleration", workflow_id="w", ranking_mode="rrf"
    )
    lexical = fuse_ranked_lists(
        ranked,
        query="AI inference acceleration",
        query_variants=["hardware acceleration for AI inference"],
        workflow_id="w",
        ranking_mode="lexical",
    )

    assert rrf[0].doi == "10.1234/noise"
    assert lexical[0].doi == "10.1234/relevant"
    assert {candidate.doi for candidate in lexical} == {
        "10.1234/noise", "10.1234/relevant",
    }
    assert lexical[0].ranking_evidence.mode == "lexical"


def test_lexical_exact_title_bonus_remains_bounded_by_rrf_evidence():
    ranked = [
        [_rec(
            "crossref", 0, doi="10.1234/consensus",
            title="Strong Provider Consensus",
        )],
        [_rec(
            "openalex", 0, doi="10.1234/consensus",
            title="Strong Provider Consensus",
        )],
        [
            *[
                _rec(
                    "web", rank, doi=f"10.1234/filler-{rank}",
                    title=f"Filler {rank}",
                )
                for rank in range(19)
            ],
            _rec(
                "web", 19, doi="10.1234/exact",
                title="AI inference acceleration",
            ),
        ],
    ]

    lexical = fuse_ranked_lists(
        ranked,
        query="AI inference acceleration",
        workflow_id="w",
        ranking_mode="lexical",
    )

    assert lexical[0].doi == "10.1234/consensus"
    exact = next(candidate for candidate in lexical if candidate.doi == "10.1234/exact")
    consensus = next(
        candidate for candidate in lexical if candidate.doi == "10.1234/consensus"
    )
    assert exact.ranking_evidence.title_relevance == 1.0
    assert exact.ranking_evidence.final_score < consensus.ranking_evidence.final_score


def test_venue_tier_never_changes_general_ranking():
    lists = [[
        _rec("crossref", 0, doi="10.1234/journal", title="Paper A", venue="IEEE Access"),
        _rec("crossref", 1, doi="10.1234/top", title="Paper B", venue="FPGA"),
    ]]

    candidates = fuse_ranked_lists(
        lists, query="paper", workflow_id="w", ranking_mode="rrf"
    )

    assert [candidate.doi for candidate in candidates] == [
        "10.1234/journal", "10.1234/top",
    ]
    assert candidates[0].venue_annotation.tier is None
    assert candidates[1].venue_annotation.tier == "top"


def test_metadata_precedence_fills_gaps_and_keeps_conflicts():
    lists = [
        [_rec("openalex", 0, doi="10.1234/x", title="OpenAlex Title",
              year=2020, venue="OA Venue")],
        [_rec("crossref", 0, doi="10.1234/x", title="Crossref Title",
              year=2021, venue="")],
        [_rec("web", 0, doi="10.1234/x", title="", year=None,
              venue="Web Venue", pid="web:u")],
    ]
    [candidate] = fuse_ranked_lists(lists, query="q", workflow_id="w")
    # Crossref outranks OpenAlex and web in precedence.
    assert candidate.title == "Crossref Title"
    assert candidate.year == 2021
    assert candidate.field_provenance["title"] == "crossref"
    # Crossref had no venue: OpenAlex fills the gap.
    assert candidate.venue == "OA Venue"
    assert candidate.field_provenance["venue"] == "openalex"
    # Conflicting values all preserved.
    title_conflicts = {c["value"] for c in candidate.conflicts["title"]}
    assert title_conflicts == {"OpenAlex Title"}
    year_conflicts = {c["value"] for c in candidate.conflicts["year"]}
    assert year_conflicts == {2020}
    venue_conflicts = {c["value"] for c in candidate.conflicts["venue"]}
    assert venue_conflicts == {"Web Venue"}


def test_work_type_uses_provider_precedence_and_keeps_conflicts():
    lists = [
        [_rec("openalex", 0, doi="10.1234/x", title="Paper",
              work_type="article")],
        [_rec("crossref", 0, doi="10.1234/x", title="Paper",
              work_type="journal-article")],
    ]

    [candidate] = fuse_ranked_lists(lists, query="paper", workflow_id="w")

    assert candidate.work_type == "journal-article"
    assert candidate.field_provenance["work_type"] == "crossref"
    assert candidate.conflicts["work_type"] == [
        {"provider": "openalex", "value": "article"}
    ]


def test_tie_break_order_doi_then_exact_title_then_provider_then_key():
    # Two rank-0 records with equal RRF: the one with a DOI wins.
    lists = [
        [_rec("web", 0, title="Exact Query", pid="web:a")],
        [_rec("openalex", 0, doi="10.1234/z", title="Something Else")],
    ]
    candidates = fuse_ranked_lists(lists, query="Exact Query", workflow_id="w")
    assert candidates[0].doi == "10.1234/z"

    # Without DOIs, exact-title match wins.
    lists = [
        [_rec("web", 0, title="Other Thing", pid="web:a")],
        [_rec("web", 0, title="Exact Query", pid="web:b")],
    ]
    candidates = fuse_ranked_lists(lists, query="Exact Query", workflow_id="w")
    assert candidates[0].title == "Exact Query"


def test_workflow_merge_cap_50():
    ranked = [
        _rec("crossref", i, doi=f"10.1234/p{i:03d}", title=f"P{i}")
        for i in range(80)
    ]
    candidates = fuse_ranked_lists([ranked], query="q", workflow_id="w")
    assert len(candidates) == 50
    assert candidates[0].doi == "10.1234/p000"


def test_workflow_cap_reserves_one_version_slot_for_each_visible_work():
    dense_versions = [
        _rec(
            "crossref", rank, doi=f"10.1234/dense-{rank}",
            title="Dense Work", year=2025, authors=["Ada Lovelace"],
        )
        for rank in range(60)
    ]
    unique_works = [
        _rec(
            "crossref", rank + 60, doi=f"10.1234/unique-{rank}",
            title=f"Unique Work {rank}", year=2025,
            authors=[f"Author {rank}"],
        )
        for rank in range(55)
    ]

    candidates = fuse_ranked_lists(
        [dense_versions + unique_works], query="work", workflow_id="w"
    )

    assert len(candidates) == 100
    assert len(representative_candidates(candidates)) == 50


def test_fusion_is_deterministic():
    lists = [
        [_rec("crossref", i, doi=f"10.1234/c{i}", title=f"C{i}") for i in range(5)],
        [_rec("openalex", i, doi=f"10.1234/c{4 - i}", title=f"C{4 - i}") for i in range(5)],
    ]
    first = fuse_ranked_lists(lists, query="q", workflow_id="w")
    second = fuse_ranked_lists(lists, query="q", workflow_id="w")
    assert [c.doi for c in first] == [c.doi for c in second]
    assert [c.candidate_id for c in first] == [c.candidate_id for c in second]
