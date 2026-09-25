# Authored teaching data

These JSON fixtures are shared by the notebooks and appbook. They contain synthetic
examples, not private customer conversations or model-generated ground truth.

`documents.json` contains 30 memories as `[id, date, subject, text]`.
`questions.json` contains 40 entries as `[id, question, relevance_grades, keyword_checks]`.
Questions q01–q12 preserve the original examples; q13–q40 extend coverage over the same
memories: corrections, historical dates, temporary preferences, project and person
differences, rejected fixes, approval roles and deployment conditions. Every question
has its own ID and wording. They are related questions over one small corpus, not 40
independent conversations. The default experiment uses q01–q06.

Relevance grades mean 1 = useful background, 2 = a connecting fact or partial answer,
and 3 = direct evidence with the correct subject and time. Unlisted source IDs have
grade 0. Precision and recall treat every positive grade as relevant; nDCG uses
`2**grade - 1` gains. Gold labels never enter provider inputs. Keyword checks are
case-insensitive substring diagnostics, so synonyms can fail and incorrect answers can
pass. Inspect sources and answers before judging factual correctness.

The original corpus and first twelve labels are unchanged. Saved notebook outputs
remain records of their earlier runs; current dataset previews appear after re-execution.
Add labeled rows here and restart the appbook to expose a larger available range.
Keep independent conversations for any production evaluation or uncertainty estimate.
