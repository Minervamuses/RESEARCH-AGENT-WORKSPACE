import asyncio
from pathlib import Path

from citation import bibtex
from citation import capture
from citation.discovery import parse_summaries
from citation.models import CaptureResult, PaperCandidate


def _bib(title: str, *, year: int | None = None, authors: str | None = None) -> str:
    fields = [f"  title = {{{title}}},"]
    if year is not None:
        fields.append(f"  year = {{{year}}},")
    if authors is not None:
        fields.append(f"  author = {{{authors}}},")
    return "@article{key,\n" + "\n".join(fields) + "\n}\n"


def test_parse_summaries_cleans_search_labels_and_extracts_doi():
    text = """Search summaries:

**1. arXiv arxiv.org › abs  › 1706.03762   [1706.03762] Attention Is All You Need**
URL: https://arxiv.org/abs/1706.03762
Description: DOI: 10.48550/arXiv.1706.03762

---

**2. ACM Digital Library dl.acm.org › doi  › 10.5555  › 3295222.3295349   Attention is all you need | Proceedings of the 31st International Conference on Neural Information Processing Systems**
URL: https://dl.acm.org/doi/10.5555/3295222.3295349
Description: No description available

---

**3. Google Scholar**
URL: https://scholar.google.com/scholar_lookup?title=Attention+is+all+you+need&amp=&author=A.+Vaswani&amp=&publication_year=2017&amp=&doi=10.48550/arXiv.1706.03762
Description: No description available

---

**4. Ashish Vaswani**
URL: https://scholar.google.com/citations?user=oR9sCGYAAAAJ&hl=en
Description: No description available

---

**5. Attention Is All You Need - Wikipedia**
URL: https://en.wikipedia.org/wiki/Attention_Is_All_You_Need
Description: No description available
"""

    candidates = parse_summaries(text)

    assert candidates[0].title == "Attention Is All You Need"
    assert candidates[0].doi == "10.48550/arXiv.1706.03762"
    assert candidates[1].title == "Attention is all you need"
    assert candidates[1].doi == "10.5555/3295222.3295349"
    assert candidates[2].title == "Attention is all you need"
    assert candidates[2].doi == "10.48550/arXiv.1706.03762"
    assert candidates[2].year == 2017
    assert candidates[2].authors == ["A. Vaswani"]
    assert len(candidates) == 3


def test_capture_retries_alternate_doi_through_crossref(monkeypatch, tmp_path):
    class Runtime:
        @property
        def cite_dir(self) -> Path:
            return tmp_path

    resolve_calls = []

    async def fake_resolve_doi(
        runtime,
        candidate,
        *,
        confirm_cb,
            result,
            allow_direct=True,
            exclude=None,
            progress_cb=None,
        ):
        resolve_calls.append((allow_direct, set(exclude or set())))
        if allow_direct:
            return "10.bad/first"
        return "10.good/second"

    def fake_fetch_bibtex_for_doi(doi):
        if doi == "10.bad/first":
            return None, ["bad DOI failed"]
        return (
            "@article{good,\n"
            "  title = {Good Paper},\n"
            "}\n",
            ["good DOI retrieved"],
        )

    monkeypatch.setattr(capture, "_resolve_doi", fake_resolve_doi)
    monkeypatch.setattr(capture, "fetch_bibtex_for_doi", fake_fetch_bibtex_for_doi)

    result = asyncio.run(
        capture.capture_citation(Runtime(), PaperCandidate("Good Paper"))
    )

    assert result.ok is True
    assert result.route == "crossref"
    assert result.doi == "10.good/second"
    assert Path(result.out_path).read_text(encoding="utf-8").startswith("@article")
    assert resolve_calls == [
        (True, set()),
        (False, {"10.bad/first"}),
    ]
    assert "bad DOI failed" in result.notes
    assert "good DOI retrieved" in result.notes


def test_verify_doi_rejects_title_mismatch():
    result = CaptureResult(ok=False)

    ok = capture._verify_doi_bibtex(
        PaperCandidate("Attention is all you need"),
        "10.1/x",
        _bib("BERT: Pre-training of Deep Bidirectional Transformers"),
        result=result,
    )

    assert ok is False
    assert any("title similarity" in note for note in result.notes)


def test_verify_doi_rejects_year_gap_greater_than_one():
    result = CaptureResult(ok=False)

    ok = capture._verify_doi_bibtex(
        PaperCandidate("Attention is all you need", year=2017),
        "10.1/x",
        _bib("Attention is all you need", year=2005),
        result=result,
    )

    assert ok is False
    assert any("year gap" in note for note in result.notes)


def test_verify_doi_rejects_explicit_author_mismatch():
    result = CaptureResult(ok=False)

    ok = capture._verify_doi_bibtex(
        PaperCandidate("Attention is all you need", authors=["A. Vaswani"]),
        "10.1/x",
        _bib(
            "Attention is all you need",
            authors="Devlin, Jacob and Chang, Ming-Wei",
        ),
        result=result,
    )

    assert ok is False
    assert any("author surname overlap" in note for note in result.notes)


def test_verify_doi_author_overlap_lowers_title_threshold():
    # Title similarity here is ~0.66: below the solo threshold (0.70) but
    # above the author-assisted one (0.55).
    bib = _bib(
        "Efficient dense passage retrieval for search",
        authors="Karpukhin, Vladimir and Oguz, Barlas",
    )

    with_overlap = capture._verify_doi_bibtex(
        PaperCandidate(
            "Retrieval efficiency in dense passage search",
            authors=["V. Karpukhin"],
        ),
        "10.1/x",
        bib,
        result=CaptureResult(ok=False),
    )
    without_authors = capture._verify_doi_bibtex(
        PaperCandidate("Retrieval efficiency in dense passage search"),
        "10.1/x",
        bib,
        result=CaptureResult(ok=False),
    )

    assert with_overlap is True
    assert without_authors is False


def test_verify_doi_passes_on_strong_title_with_unknown_year_and_authors():
    result = CaptureResult(ok=False)

    ok = capture._verify_doi_bibtex(
        PaperCandidate("Attention is all you need"),
        "10.1/x",
        _bib("Attention is all you need"),
        result=result,
    )

    assert ok is True
    assert any("DOI verified" in note for note in result.notes)


def test_capture_excludes_verification_failed_doi_and_uses_alternate(monkeypatch, tmp_path):
    class Runtime:
        @property
        def cite_dir(self) -> Path:
            return tmp_path

    resolve_calls = []

    async def fake_resolve_doi(
        runtime,
        candidate,
        *,
        confirm_cb,
        result,
        allow_direct=True,
        exclude=None,
        progress_cb=None,
    ):
        resolve_calls.append((allow_direct, set(exclude or set())))
        return "10.bad/mismatch" if allow_direct else "10.good/verified"

    def fake_fetch_bibtex_for_doi(doi):
        if doi == "10.bad/mismatch":
            return _bib("A Totally Unrelated Compendium of Rocks"), ["mismatch retrieved"]
        return _bib("Good Paper"), ["good retrieved"]

    monkeypatch.setattr(capture, "_resolve_doi", fake_resolve_doi)
    monkeypatch.setattr(capture, "fetch_bibtex_for_doi", fake_fetch_bibtex_for_doi)

    result = asyncio.run(
        capture.capture_citation(Runtime(), PaperCandidate("Good Paper"))
    )

    assert result.ok is True
    assert result.doi == "10.good/verified"
    assert resolve_calls == [
        (True, set()),
        (False, {"10.bad/mismatch"}),
    ]
    assert any(
        "DOI verification failed for 10.bad/mismatch" in note for note in result.notes
    )
    # only the verified BibTeX reached disk
    assert [p.name for p in tmp_path.iterdir()] == ["good_paper.bib"]


def test_capture_writes_nothing_when_no_doi_verifies(monkeypatch, tmp_path):
    class Runtime:
        @property
        def cite_dir(self) -> Path:
            return tmp_path

    async def fake_resolve_doi(
        runtime,
        candidate,
        *,
        confirm_cb,
        result,
        allow_direct=True,
        exclude=None,
        progress_cb=None,
    ):
        return "10.bad/mismatch" if allow_direct else None

    monkeypatch.setattr(capture, "_resolve_doi", fake_resolve_doi)
    monkeypatch.setattr(
        capture,
        "fetch_bibtex_for_doi",
        lambda doi: (_bib("A Totally Unrelated Compendium of Rocks"), ["retrieved"]),
    )

    result = asyncio.run(
        capture.capture_citation(Runtime(), PaperCandidate("Good Paper"))
    )

    assert result.ok is False
    assert list(tmp_path.iterdir()) == []
    assert any("DOI verification failed" in note for note in result.notes)


def test_bibtex_title_extraction_handles_single_line_crossref_bibtex():
    one_line = (
        "@article{Mohaidat_2024, title={A Survey on Neural Network Hardware "
        "Accelerators}, volume={5}, ISSN={2691-4581}, "
        "url={http://dx.doi.org/10.1109/TAI.2024.3377147}, "
        "DOI={10.1109/tai.2024.3377147}, number={8}, journal={IEEE "
        "Transactions on Artificial Intelligence}, publisher={Institute of "
        "Electrical and Electronics Engineers (IEEE)}, author={Mohaidat, "
        "Tamador and Khalil, Kasem}, year={2024}, month=aug, pages={3801-3822} }"
    )

    assert (
        bibtex.extract_bibtex_title(one_line)
        == "A Survey on Neural Network Hardware Accelerators"
    )
    assert (
        bibtex.normalize_title_to_filename(bibtex.extract_bibtex_title(one_line))
        == "a_survey_on_neural_network_hardware_accelerators.bib"
    )


def test_normalized_bibtex_filename_is_length_capped():
    filename = bibtex.normalize_title_to_filename("x" * 400)

    assert filename.endswith(".bib")
    assert len(filename.removesuffix(".bib")) <= 160
