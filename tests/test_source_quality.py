"""Source-question status: deterministic rules + the rule that an LLM screen can never mark a question ILL_POSED."""
from src.extraction import source_quality as sq


def test_clean_question_is_valid():
    assert sq.deterministic_status("Explain the working of a semaphore with an example.")[0] == sq.VALID


def test_short_three_word_definition_is_valid_but_fragment_is_not():
    assert sq.deterministic_status("Define routing protocol.")[0] == sq.VALID
    assert sq.deterministic_status("Let")[0] == sq.EXTRACTION_ERROR


def test_list_markers_are_not_unbalanced_brackets():
    assert sq.deterministic_status("i) Prove that the sum is even. ii) Draw the graph for each case.")[0] == sq.VALID
    assert sq.deterministic_status("Find the value of (3 + (4 * 2).")[0] == sq.EXTRACTION_ERROR


def test_dangling_data_is_incomplete_not_deleted():
    st, why = sq.deterministic_status("Determine the shortest path using the weighted graph given below:")
    assert st == sq.INCOMPLETE and any("colon" in w or "refers" in w for w in why)


def test_llm_screen_can_only_raise_needs_human_review():
    st, why = sq.combine(sq.VALID, [], {"answerable": False, "ambiguous": True})
    assert st == sq.NEEDS_REVIEW and all(w.startswith("llm_screen:") for w in why)
    assert sq.combine(sq.VALID, [], {"answerable": True, "ambiguous": False})[0] == sq.VALID
    # a deterministic defect is never overwritten by the LLM
    assert sq.combine(sq.EXTRACTION_ERROR, ["x"], {"answerable": True})[0] == sq.EXTRACTION_ERROR
    assert "ILL_POSED" not in {sq.VALID, sq.EXTRACTION_ERROR, sq.INCOMPLETE, sq.NEEDS_REVIEW}


def test_exemplar_eligibility_excludes_only_deterministic_defects():
    assert sq.eligible_for_exemplars(sq.VALID) and sq.eligible_for_exemplars(sq.NEEDS_REVIEW)
    assert not sq.eligible_for_exemplars(sq.EXTRACTION_ERROR) and not sq.eligible_for_exemplars(sq.INCOMPLETE)
