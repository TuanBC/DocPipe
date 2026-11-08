# Stakeholder interviews: plan and notes

**Status: not yet held.** The brief asks for at least 5 people across at least 3 roles. Until these rows are filled
with real conversations, every stakeholder statement in the memo is labelled as public-source or simulated.
Fill one block per conversation; keep quotes verbatim; mark anything you infer as inference.

## Who to talk to (5 people, 4 roles)

| # | Role | Why this person | Status |
|---|---|---|---|
| 1 | Corporate credit analyst (user) | Does the spreading and filing today | To schedule |
| 2 | Relationship manager, SME or corporate (user) | Collects onboarding documents from customers | To schedule |
| 3 | Credit operations lead (process owner) | Owns volumes, SLAs, the filing standard | To schedule |
| 4 | Risk / compliance officer | Decides what evidence an AI-assisted step needs and where data may go | To schedule |
| 5 | Platform / data engineer (technology) | Knows hosting, approved models, integration points | To schedule |

## Questions (30 minutes)

All: walk me through the last credit file you handled, from receiving the documents to the decision. Where did the
time go? What went wrong?

- **Analyst / RM**: how many documents per file, and which take longest? How do you find the statement pages? How do
  you key numbers (template, system)? Errors you caught or missed? What would you need to see to trust a pre-filled
  spread or an auto-filed folder?
- **Operations**: monthly volume by document type; rework rate; SLA; how files are named and found; what an exception
  costs; how many reviewers could absorb a queue?
- **Risk / compliance**: what evidence is needed for an AI-assisted step; which data may go to an external model;
  who approves a model change; audit and retention expectations; what would make you stop it?
- **Technology**: where documents live today (DMS, shared drives, LOS); integration points; hosting constraints;
  approved models and vector stores; licence policy (AGPL?).

## Notes template

```
### Interview N
- Role / team:                 - Date:            - Real or simulated: REAL
- Three verbatim quotes:
  1.
  2.
  3.
- One number (with unit and how they know it):
- Biggest pain:
- What would make them trust / reject the tool:
- Conflict with another role (who, about what):
- Changes this implies for the design or the business case:
```

## Conflicts log (fill after the interviews)

| Between | About | How the design responds |
|---|---|---|
| | | |
