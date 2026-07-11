"""Versioned venue catalog: exact aliases, provenance, and fail-open unknowns."""

from importlib import resources

from skills.citation.venue import (
    annotate_venue,
    load_venue_catalog,
    normalize_venue_name,
)


def test_catalog_aliases_are_normalized_but_not_fuzzy():
    fpga = annotate_venue("ＡＣＭ　ＦＰＧＡ")
    assert fpga.canonical_name.startswith("ACM/SIGDA")
    assert fpga.kind == "conference"
    assert fpga.tier == "top"

    unknown = annotate_venue("FPGA adjacent workshop")
    assert unknown.kind == "unclassified"
    assert unknown.tier is None


def test_repository_and_journal_do_not_infer_prestige():
    ssrn = annotate_venue("SSRN Electronic Journal")
    access = annotate_venue("IEEE Access")
    assert (ssrn.kind, ssrn.tier) == ("repository", None)
    assert (access.kind, access.tier) == ("journal", None)


def test_catalog_has_version_source_and_package_resource():
    catalog = load_venue_catalog()
    assert catalog.version == "2026.07-v1"
    assert catalog.source
    resource = resources.files("skills.citation").joinpath("venue_catalog.yaml")
    assert resource.is_file()
    assert normalize_venue_name("IEEE/ACM MICRO") == "ieee acm micro"
