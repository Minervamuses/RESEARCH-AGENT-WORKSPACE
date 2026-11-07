"""Project CSL-JSON bibliography: load, layout, keys, merge, atomic write."""

import difflib
import json
import os

import pytest

from skills.citation import library as lib
from skills.citation.library import LibraryError

USER_ITEMS = [
    {
        "id": "agrawal2024references",
        "type": "article-journal",
        "title": "Do language models know when they’re hallucinating references?",
        "author": [{"family": "Agrawal", "given": "Ayush"}],
        "issued": {"date-parts": [[2024]]},
        "container-title": "Findings of EACL",
        "page": "912–928",
        "DOI": "10.18653/V1/2024.FINDINGS-EACL.62",
    },
    {
        "id": "fao2023site",
        "type": "webpage",
        "title": "FAOSTAT",
        "author": [{"literal": "Food and Agriculture Organization"}],
        "issued": {"date-parts": [[2023]]},
        "URL": "https://www.fao.org/faostat/",
    },
    {
        "id": "vaswani2017attention",
        "type": "article",
        "title": "Attention is all you need",
        "author": [{"family": "Vaswani", "given": "Ashish"}],
        "issued": {"date-parts": [[2017]]},
        "URL": "https://arxiv.org/abs/1706.03762v7",
    },
]


def _write_user_file(tmp_path, items=USER_ITEMS, indent=1):
    path = tmp_path / "references.json"
    path.write_text(json.dumps(items, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    return path


NEW = {
    "type": "article-journal",
    "title": "The structure of crops",
    "author": [{"family": "Smith", "given": "Jane"}],
    "issued": {"date-parts": [[2020, 3]]},
    "DOI": "10.1000/xyz",
}


def test_adding_one_entry_only_appends_at_the_tail(tmp_path):
    path = _write_user_file(tmp_path)
    before = path.read_text(encoding="utf-8")

    result = lib.add_item(path, NEW)

    after = path.read_text(encoding="utf-8")
    assert result.status == "added"
    assert result.key == "smith2020structure"
    diff = [
        line for line in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0)
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    # Purely additive: the new entry is inserted before the previous last
    # entry's closing brace, so no existing line changes.
    assert [line for line in diff if line.startswith("-")] == []
    assert after.startswith(before[: before.rindex(" }")])
    assert after.endswith(" }\n]\n")
    assert json.loads(after)[:3] == USER_ITEMS
    assert json.loads(after)[3]["id"] == "smith2020structure"
    assert "–" in after and "\\u2013" not in after


def test_same_doi_with_different_case_reuses_entry_and_does_not_write(tmp_path):
    path = _write_user_file(tmp_path)
    before = path.read_bytes()
    result = lib.add_item(path, {**NEW, "DOI": "10.18653/v1/2024.findings-eacl.62"})
    assert result.status == "existing"
    assert result.key == "agrawal2024references"
    assert path.read_bytes() == before


def test_arxiv_id_reuses_hand_written_entry(tmp_path):
    path = _write_user_file(tmp_path)
    before = path.read_bytes()
    item = {"type": "article", "title": "Attention", "number": "1706.03762",
            "publisher": "arXiv", "URL": "https://arxiv.org/abs/1706.03762"}
    result = lib.add_item(path, item)
    assert (result.status, result.key) == ("existing", "vaswani2017attention")
    assert path.read_bytes() == before
    doi_form = {"type": "article", "DOI": "10.48550/arXiv.1706.03762"}
    assert lib.add_item(path, doi_form).key == "vaswani2017attention"


NEURIPS_HASH = "3f5ee243547dee91fbd053c1c4a845aa"


def test_neurips_identity_comes_from_the_official_proceedings_url():
    for url in (
        f"https://papers.nips.cc/paper_files/paper/2017/hash/{NEURIPS_HASH}-Abstract.html",
        f"https://proceedings.neurips.cc/paper_files/paper/2017/hash/{NEURIPS_HASH}-Abstract.html",
        f"https://proceedings.neurips.cc/paper_files/paper/2017/file/{NEURIPS_HASH}-Paper.pdf",
        f"http://PAPERS.NIPS.CC/paper/2017/hash/{NEURIPS_HASH.upper()}-Abstract.html",
    ):
        assert lib.item_neurips({"URL": url}) == f"neurips:2017:{NEURIPS_HASH}", url
    for url in (
        None, "", "https://example.org/paper_files/paper/2017/hash/" + NEURIPS_HASH + "-Abstract.html",
        "https://datasets-benchmarks-proceedings.neurips.cc/paper_files/paper/2021/hash/"
        "65b9eea6e1cc6bb9f0cd2a47751a186f-Abstract-round2.html",
        "https://proceedings.neurips.cc/paper_files/paper/2017",
        "https://papers.nips.cc/paper/7181-attention-is-all-you-need",
    ):
        assert lib.item_neurips({"URL": url}) is None, url


def test_neurips_paper_reuses_the_entry_with_either_host(tmp_path):
    hand = {"id": "vaswani2017attention", "type": "paper-conference", "title": "Attention Is All You Need",
            "URL": f"https://papers.nips.cc/paper_files/paper/2017/hash/{NEURIPS_HASH}-Abstract.html"}
    path = tmp_path / "references.json"
    path.write_text(json.dumps([hand], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    before = path.read_bytes()
    saved = {"type": "paper-conference", "title": "Attention is All you Need",
             "URL": f"https://proceedings.neurips.cc/paper_files/paper/2017/hash/{NEURIPS_HASH}-Abstract.html"}
    assert (lib.add_item(path, saved).status, lib.add_item(path, saved).key) == ("existing", "vaswani2017attention")
    assert path.read_bytes() == before
    other = {**saved, "URL": saved["URL"].replace(NEURIPS_HASH, "3f647cadf56541fb9513cb63ec370187")}
    assert lib.add_item(path, other).status == "added"


def test_key_collision_gets_letter_suffix(tmp_path):
    path = _write_user_file(tmp_path)
    first = lib.add_item(path, NEW)
    second = lib.add_item(path, {**NEW, "DOI": "10.1000/other"})
    third = lib.add_item(path, {**NEW, "DOI": "10.1000/third"})
    assert [first.key, second.key, third.key] == [
        "smith2020structure", "smith2020structurea", "smith2020structureb",
    ]


def test_key_rules():
    assert lib.base_key({"author": [{"family": "王"}], "issued": {"date-parts": [[2021]]},
                         "title": "水稻研究"}) == "ref2021"
    assert lib.base_key({"author": [{"family": "Müller-Lüdenscheidt"}],
                         "title": "On the Ünïcode", "issued": {"date-parts": [[1999]]}}) \
        == "mullerludenscheidt1999unicode"
    assert lib.base_key({"author": [{"literal": "World Health Organization"}],
                         "title": "A report"}) == "worldndreport"
    assert lib.base_key({"title": "The <i>Big</i> Data"}) == "refndbig"
    assert lib.base_key({}) == "refnd"


def test_unknown_layout_is_not_written(tmp_path):
    path = tmp_path / "references.json"
    path.write_text(json.dumps(USER_ITEMS, indent=3), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(LibraryError) as excinfo:
        lib.add_item(path, NEW)
    assert excinfo.value.code == lib.LIBRARY_FORMAT_UNSUPPORTED
    assert path.read_bytes() == before


@pytest.mark.parametrize("indent", [2, 4, "\t"])
def test_other_known_layouts_are_preserved(tmp_path, indent):
    path = _write_user_file(tmp_path, indent=indent)
    lib.add_item(path, NEW)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert path.read_text(encoding="utf-8") == json.dumps(data, ensure_ascii=False, indent=indent) + "\n"


@pytest.mark.parametrize("payload", [
    "{}", "[1]", '[{"title": "no id"}]', '[{"id": "a"}, {"id": "a"}]', "not json",
])
def test_malformed_files_are_rejected_and_not_written(tmp_path, payload):
    path = tmp_path / "references.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(LibraryError) as excinfo:
        lib.add_item(path, NEW)
    assert excinfo.value.code == lib.LIBRARY_MALFORMED
    assert path.read_text(encoding="utf-8") == payload


def test_change_on_disk_before_write_is_a_conflict(tmp_path):
    path = _write_user_file(tmp_path)
    library = lib.load(path)
    result = lib.merge(library, NEW)
    path.write_text(path.read_text(encoding="utf-8").replace("FAOSTAT", "FAOSTAT!"), encoding="utf-8")
    changed = path.read_bytes()
    with pytest.raises(LibraryError) as excinfo:
        lib.write_atomic(result.library)
    assert excinfo.value.code == lib.LIBRARY_CONFLICT
    assert path.read_bytes() == changed
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]


def test_missing_file_is_created_with_new_file_layout(tmp_path):
    path = tmp_path / "references.json"
    result = lib.add_item(path, NEW)
    assert result.status == "added"
    text = path.read_text(encoding="utf-8")
    assert text == json.dumps([{"id": "smith2020structure", **NEW}], ensure_ascii=False, indent=1) + "\n"
    assert lib.load(path).layout == 1


def test_write_preserves_file_mode(tmp_path):
    path = _write_user_file(tmp_path)
    os.chmod(path, 0o640)
    lib.add_item(path, NEW)
    assert (path.stat().st_mode & 0o777) == 0o640


def test_merge_does_not_mutate_input_library(tmp_path):
    path = _write_user_file(tmp_path)
    library = lib.load(path)
    result = lib.merge(library, NEW)
    assert len(library.items) == 3
    assert len(result.library.items) == 4


def test_arxiv_number_prefix_is_enough_to_match():
    assert lib.item_arxiv({"number": "arXiv:2404.01268"}) == "2404.01268"
    assert lib.item_arxiv({"number": "2404.01268"}) is None
    assert lib.item_arxiv({"number": "2404.01268", "publisher": "arXiv"}) == "2404.01268"


def test_unknown_layout_is_readable_and_reuse_needs_no_write(tmp_path):
    path = tmp_path / "references.json"
    path.write_text(json.dumps(USER_ITEMS, separators=(",", ":")), encoding="utf-8")
    before = path.read_bytes()
    library = lib.load(path)
    assert library.layout is None and len(library.items) == 3
    assert lib.add_item(path, {"DOI": "10.18653/v1/2024.findings-eacl.62"}).status == "existing"
    assert path.read_bytes() == before
