# Evaluation report — efta_faqs_v0

- Document: `samples/cfpb_efta_faqs.pdf`
- limit: `5`
- base_url: `http://127.0.0.1:8000`
- date: `2026-11-15`
- label: `prompt-v3-run1`

## Summary

| Metric | Result |
|---|---|
| retrieval_hit | 7/7 |
| citation_hit | 6/7 |
| keyword_match | 6/7 |
| answered_when_answerable | 6/7 |
| abstained_when_unanswerable | 3/3 |
| median_latency_ms | 1106 |

## Per question

| ID | Type | Top distance | Retrieved pages | Retrieval | Cited pages | Citation | Keywords | Abstained | Correct behaviour | Latency ms |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | direct | 0.133 | [2, 2, 1, 13, 6] | ✅ | [2, 2, 1, 13, 6] | ✅ | ✅ | False | ✅ | 2003 |
| q02 | paraphrase | 0.231 | [11, 11, 13, 12, 12] | ✅ | [11, 11, 13, 12, 12] | ✅ | ✅ | False | ✅ | 3113 |
| q03 | paraphrase | 0.317 | [7, 3, 12, 13, 13] | ✅ | [7, 3, 12, 13, 13] | ✅ | ✅ | False | ✅ | 1106 |
| q04 | exact_identifier | 0.144 | [4, 6, 15, 5, 5] | ✅ | [4, 6, 15, 5, 5] | ✅ | ✅ | False | ✅ | 1041 |
| q05 | exact_number | 0.144 | [8, 9, 14, 8, 9] | ✅ | [8, 9, 14, 8, 9] | ✅ | ✅ | False | ✅ | 1017 |
| q06 | page_specific | 0.221 | [8, 5, 6, 7, 13] | ✅ | [8, 5, 6, 7, 13] | ✅ | ✅ | False | ✅ | 1141 |
| q07 | exact_identifier | 0.310 | [9, 14, 14, 9, 8] | ✅ | [] | ❌ | ❌ | True | ❌ | 1092 |
| q08 | unanswerable_in_domain | 0.318 | [9, 10, 8, 7, 9] | – | [] | – | – | True | ✅ | 1101 |
| q09 | unanswerable_near_domain | 0.366 | [2, 3, 2, 3, 7] | – | [] | – | – | True | ✅ | 1785 |
| q10 | unanswerable_off_domain | 0.588 | [7, 4, 10, 13, 8] | – | [] | – | – | True | ✅ | 88 |

## Answers

- **q01**: Yes.
- **q02**: Yes. Under Regulation E, when a third party fraudulently induces a consumer into sharing their account login information and then uses that information to make an electronic fund transfer from the consumer's account, the transfer is considered an unauthorized electronic fund transfer (unauthorized EFT).
- **q03**: No. According to the evidence, a financial institution cannot consider a consumer's negligence when determining liability for unauthorized EFTs under Regulation E, and consumer behavior that may constitute negligence—such as writing the PIN on a debit card or on a piece of paper kept with the card—does not affect the consumer's liability.
- **q04**: Regulation E section 1005.2(i) defines a financial institution under EFTA and Regulation E.
- **q05**: Within three business days after completing its investigation.
- **q06**: Based on the provided evidence, the term "error" does not include the following consumer requests:

- A routine inquiry about the consumer's account balance
- A request for information for tax or other recordkeeping purposes
- A request for duplicate copies of documentation
- **q07**: Insufficient evidence in the indexed documents to answer that.
- **q08**: Insufficient evidence in the indexed documents to answer that.
- **q09**: Insufficient evidence in the indexed documents to answer that.
- **q10**: Insufficient evidence in the indexed documents to answer that.
