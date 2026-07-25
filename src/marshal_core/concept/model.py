"""概念页领域模型 + frontmatter 解析。markdown 是真相源, 这里只做只读解析。"""
from dataclasses import dataclass, field

import yaml

_VALID_IMPORTANCE = {"constitutional", "high", "mid", "low"}


class NotAConceptPage(ValueError):
    """页面不是概念页(无 frontmatter 或无 concept_id)—— derive 应静默跳过, 非错误。
    与"格式错的概念页"(有 concept_id 但 anchor/importance 非法, 抛普通 ValueError)区分:
    后者是真 typo, 不能被静默吞掉(深审 run 750 bug C)。"""


@dataclass
class ConceptAnchor:
    repo: str
    path: str
    symbol: str
    kind: str = "implements"


@dataclass
class ConceptPage:
    concept_id: str
    importance: str
    parent: str = ""
    part_of: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    anchors: list[ConceptAnchor] = field(default_factory=list)
    spec_refs: list[str] = field(default_factory=list)
    status: str = "draft"
    definition: str = ""


def parse_concept_page(text: str) -> ConceptPage:
    """把一页 markdown(frontmatter + body)解析成 ConceptPage。字段缺失即报错,
    不静默给默认 —— 概念真相源必须显式。非概念页抛 NotAConceptPage(可跳过);
    概念页格式错抛 ValueError(是 typo, 不可静默吞)。"""
    if not text.startswith("---"):
        raise NotAConceptPage("not a concept page: missing YAML frontmatter (---)")
    _, fm_raw, body = text.split("---", 2)
    fm = yaml.safe_load(fm_raw) or {}

    concept_id = fm.get("concept_id")
    if not concept_id:
        raise NotAConceptPage("not a concept page: frontmatter has no 'concept_id'")
    importance = fm.get("importance")
    if importance not in _VALID_IMPORTANCE:
        raise ValueError(f"invalid importance {importance!r}; want one of {_VALID_IMPORTANCE}")

    try:
        anchors = [
            ConceptAnchor(repo=a["repo"], path=a["path"], symbol=a["symbol"],
                          kind=a.get("kind", "implements"))
            for a in (fm.get("anchors") or [])
        ]
    except (KeyError, TypeError) as e:   # 缺字段/格式错 → ValueError (深审 bug C: 别抛 KeyError 崩批)
        raise ValueError(f"malformed anchor in concept {concept_id!r}: missing field {e}") from e
    return ConceptPage(
        concept_id=concept_id,
        importance=importance,
        parent=fm.get("parent", "") or "",
        part_of=list(fm.get("part_of") or []),
        depends_on=list(fm.get("depends_on") or []),
        anchors=anchors,
        spec_refs=list(fm.get("spec_refs") or []),
        status=fm.get("status", "draft"),
        definition=body.strip(),
    )
