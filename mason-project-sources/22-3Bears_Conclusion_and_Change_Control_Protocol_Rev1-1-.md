# 3BEARS CONCLUSION & CHANGE-CONTROL PROTOCOL
## Controlling Standard for Project, Estimate, Review and Development Completion

**Revision:** Rev1  
**Effective date:** 10 September 2026  
**Status:** CONTROLLING STANDARD — use once added to Project Files / Source Files  
**Applies to:** Estimating, estimating-system development, Independent Estimate Review Board work, software/tool development, documents, reports, workflow packs, AI-assisted projects and other controlled work products.

---

# 1. PURPOSE

This standard defines **when work is finished, when the AI must stop refining it, how a completed result is baselined, and what authority is required to change it later**.

A chat has no natural end state. Without a control rule, every new question, observation or idea can produce another output and can unintentionally cause completed work to keep changing.

This protocol replaces that behaviour with a controlled lifecycle.

> **Work continues until the agreed objective and Definition of Done are satisfied. Once the remaining reasonably achievable improvement is immaterial to the purpose of the work, the current version is concluded and baselined. Further conversation does not alter that baseline unless an explicit change instruction is given.**

The objective is not perfection.

The objective is the **best reasonably achievable, evidence-based and decision-useful result at the point of release**.

---

# 2. CORE CONCLUSION PRINCIPLE

A controlled work product is considered ready to conclude when all of the following are true:

1. The agreed objective has been achieved.
2. The required deliverables exist.
3. The applicable Definition of Done has been satisfied.
4. Required verification and reconciliation tests have passed.
5. Remaining uncertainty is visible, classified and appropriately treated.
6. No unresolved issue remains that would reasonably change the release decision, scope basis, price, programme, compliance position, risk allocation or other material outcome.
7. Further reasonably available analysis is unlikely to produce a **material improvement** in accuracy or decision quality.
8. Any remaining improvement opportunities are enhancements, not completion requirements.
9. The required approval authority has accepted the release, where approval is required.

When these conditions are met:

> **CALL IT DONE.**

Do not continue improving the current version simply because another possible improvement can be imagined.

---

# 3. DONE DOES NOT MEAN PERFECT

Completion is not defined as:

- zero uncertainty
- zero assumptions
- every possible source having been searched
- every possible alternative having been modelled
- every AMBER item becoming GREEN
- no future improvement being possible
- absolute certainty about future events

Those standards would make completion impossible.

Completion means:

> **The work is as complete, accurate and verified as can reasonably be justified from the evidence available for its stated purpose, and further work is not expected to materially improve the decision being made.**

A forecast can be complete while still containing disclosed uncertainty.

An estimate can be complete while still containing properly controlled allowances, provisional quantities, PC sums, qualifications or accepted AMBER items.

A project can be complete even though a better method may be discovered in the future.

Future improvement belongs to the next controlled version.

---

# 4. THE MATERIALITY / DIMINISHING-RETURN TEST

This is the primary stop test.

Before continuing another round of refinement, ask:

> **Is there a reasonable prospect that the next piece of work will materially improve the accuracy, completeness, defensibility or decision usefulness of the result?**

Continue only where the answer is **Yes**.

A proposed refinement is material if it could reasonably:

- change the overall commercial decision
- change the estimate or a major cost package beyond the project's nominated materiality tolerance
- change scope inclusion, exclusion or package ownership
- change a material quantity, rate, productivity, methodology or resource requirement
- change the critical path, working duration or material time-related cost
- expose or remove a material risk
- change GREEN / AMBER / RED verification status in a way that matters to release
- change compliance, safety, contractual or technical acceptability
- correct a genuine error, omission, duplication or broken cost path
- materially improve the ability to defend the result later

A proposed refinement is normally **immaterial** if it:

- only changes wording without changing meaning or release usefulness
- produces trivial numerical movement relative to the purpose of the estimate
- adds detail that does not affect a decision
- repeats a verification already adequately completed
- searches for additional evidence when the current evidence is already sufficient for the required confidence level
- optimises presentation beyond the agreed standard
- explores hypothetical alternatives that have not been instructed
- represents a possible future enhancement rather than a defect in the current deliverable

If the likely effect is immaterial, record the idea if useful and **stop refining the current version**.

---

# 5. NO UNIVERSAL PERCENTAGE FOR "DONE"

There is no single percentage movement that defines materiality for every project.

A $5,000 movement may be immaterial on one project and decisive on another.

Where useful, the project intake or workstream brief should nominate a **Completion Materiality Tolerance**, expressed as:

- a dollar amount
- a percentage
- a package-specific threshold
- a programme threshold
- a decision-based threshold
- or a combination of these

If no numerical tolerance has been nominated, use the **Reasonable Decision Test**:

> **Would a competent estimator, PM, reviewer, client or decision-maker reasonably make a different decision if this remaining refinement were completed?**

If **No**, and there is no unresolved correctness, safety, compliance, scope or release issue, the refinement is not grounds to keep the current version open.

Do not invent a percentage simply to force a completion decision.

---

# 6. PRECISION CEILING

Every project has an evidence ceiling.

The work must not be represented as more precise than the available evidence supports.

Once the analysis has reached the practical precision supported by:

- the drawings and specifications
- available supplier evidence
- measurement quality
- productivity evidence
- project information
- programme definition
- risk evidence
- actual/historical data
- and the estimate level

additional calculation can create **false precision rather than greater truth**.

When the evidence ceiling has been reached:

> **Further mathematical refinement is not automatically an improvement.**

The correct response may be to release the estimate with an explicit allowance, provisional item, qualification, RFI, AMBER status or stated range rather than continue calculating.

---

# 7. LIFECYCLE STATES

Every controlled work product must use one of the following lifecycle states.

## 7.1 WORKING

Active development.

New evidence, corrections and approved design decisions may change the work.

Normal conversation may result in modification.

---

## 7.2 REVIEW

The work is substantially complete and is being checked.

Permitted activity includes:

- verification
- reconciliation
- red-team review
- error correction
- completeness checks
- release-gate checks
- closure of material RFIs / verification actions

New ideas are **not automatically incorporated** merely because they arise during review.

Ideas not required to satisfy the Definition of Done become future enhancements.

---

## 7.3 READY FOR RELEASE

The objective and Definition of Done have been satisfied.

No unresolved release blocker remains.

Further reasonably available refinement is not expected to materially improve the current result.

The AI should state:

> **CONCLUSION RECOMMENDED — The agreed objective and Definition of Done have been satisfied. Further work is not expected to materially improve the current result. I recommend this version be released and baselined.**

READY FOR RELEASE is not yet authority to alter release records or declare user approval where approval is required.

---

## 7.4 RELEASED / BASELINED

The approved current version is frozen.

Record at minimum:

- artifact / workstream name
- revision
- release date
- lifecycle status
- verification / confidence status
- approval authority
- governing source versions
- accepted AMBER items
- unresolved items, if release rules allow any
- superseded revision
- controlled file / baseline location

A released baseline is **immutable**.

Do not silently edit it.

---

## 7.5 CHANGE CONTROL / REOPENED

The released baseline remains preserved.

A change is being assessed or developed under explicit authority.

The change must identify:

- Change ID
- reason
- requested by
- affected artifact / revision
- affected scope
- cost impact
- programme impact
- risk / verification impact
- affected source documents
- approval status
- new revision if approved

Approved changes create a **new revision**.

They do not overwrite history.

---

## 7.6 CLOSED / ARCHIVED

The current workstream or project phase is complete.

There is no outstanding action required to achieve its stated objective.

The final baseline, release record, handoff/recovery record and relevant evidence have been retained.

Further work requires:

- a new workstream
- a new revision
- a formal change
- or an explicit reopening instruction

---

# 8. VERIFICATION STATUS IS SEPARATE FROM LIFECYCLE STATUS

Do not confuse verification/confidence status with lifecycle status.

Examples:

- **REVIEW / GREEN**
- **READY FOR RELEASE / AMBER**
- **RELEASED / GREEN**
- **RELEASED / AMBER with disclosed limitations**
- **WORKING / RED**
- **HOLD / RED**

GREEN / AMBER / RED describes evidence and verification.

WORKING / REVIEW / READY / RELEASED / REOPENED / CLOSED describes the lifecycle.

A work product can be highly verified but not yet released.

A released tender may contain accepted and disclosed AMBER items where the governing release standard permits this.

An unresolved material RED item remains a release blocker unless the governing standard expressly allows it to be excluded, transferred or formally accepted.

---

# 9. DEFINITION OF DONE MUST BE SET EARLY

Every controlled project or workstream should define, as early as practical:

**Objective**  
What problem are we solving?

**Deliverables**  
What must physically exist?

**Definition of Done**  
What conditions must be satisfied?

**Materiality basis**  
What level of remaining change would matter?

**Approval Authority**  
Who can release / approve the work?

**Lifecycle State**  
Where is the work currently?

If the user has not expressly nominated every field, infer only what is safely supported by the governing project standard and current brief.

Do not invent a technical, commercial or contractual acceptance criterion.

---

# 10. ESTIMATE-SPECIFIC DEFINITION OF DONE

For a tender or equivalent detailed estimate, completion should normally require, where applicable:

1. Nominated work-package scope accounted for.
2. Cross-discipline scope sweep completed.
3. Active QS items linked to controlling source evidence.
4. Materials & Component coverage complete or explicitly classified.
5. Required markups completed and reconciled.
6. Resource Build-Up linked to QS Takeoff.
7. QS Takeoff reconciled to Tender Build-Up.
8. Tender Build-Up reconciled to Summary.
9. Summary / Cashflow reconciliation completed where applicable.
10. Major quantities checked.
11. Major rates checked to the required verification level.
12. Labour, plant, materials and subcontract resources accounted for.
13. Productivity and crew assumptions have a stated basis.
14. Programme reconciled with quantities, productivity and time-related cost.
15. Productive crew days, working days and elapsed calendar days correctly distinguished.
16. Weather model completed where applicable and current with programme inputs.
17. Risk Truth completed for material project risks.
18. No unexplained duplicate cost paths.
19. Commercial inputs complete.
20. Company overhead recovery and contractor profit correctly applied and separated.
21. Assumptions, exclusions, interfaces, provisional items and RFIs documented.
22. Required client report / tender basis report produced.
23. Required programme / programme export produced.
24. Governing document revisions recorded.
25. Required verification/review board process completed where applicable.
26. No unresolved material RED release blocker remains.
27. Final price and programme reconciliation passed.
28. Remaining uncertainty is properly disclosed and is not being disguised by false precision.
29. Marginal-value test passed: further reasonably available work is not expected to materially improve the estimate for its stated purpose.
30. Release recommendation / approval recorded.

Once these conditions are met, the estimate should be called done for that revision.

---

# 11. DEVELOPMENT-WORKSTREAM DEFINITION OF DONE

A system-development workstream should normally conclude when:

1. The problem was clearly defined.
2. The methodology was defined.
3. Required evidence and source basis were identified.
4. A prototype was built where required.
5. The method was tested on a representative real case.
6. The result was red-teamed.
7. Existing functionality was preserved.
8. Required cost/programme/data integrations were tested.
9. Duplicate or competing authority paths were removed.
10. Changed inputs propagate correctly.
11. Known limitations are visible.
12. The workstream is demonstrably better than the prior method for its stated purpose.
13. Required governing instructions have been updated or a deliberate decision made not to update them.
14. Recovery / handoff information has been produced.
15. There are no unresolved defects that materially undermine the workstream objective.
16. Further proposed improvements are enhancements rather than requirements to solve the original problem.
17. The marginal-value test has passed.

At this point the workstream must be recommended for closure.

Do not keep the workstream open merely to continue optimisation.

---

# 12. AI DUTY TO SEEK A CONCLUSION

The AI must actively manage toward completion.

It must not:

- indefinitely expand scope
- continue researching without a material reason
- redesign a working solution merely because another approach exists
- reopen settled decisions without new evidence
- treat every user observation as an instruction to modify
- keep adding features after the stated objective has been achieved
- turn a released baseline back into a working version without explicit authority

The AI must periodically assess:

> **Are we still solving the agreed problem, or are we now improving a solution that is already good enough to release?**

When the latter is true, the AI should recommend conclusion.

---

# 13. POST-RELEASE CONVERSATION IS DISCUSSION BY DEFAULT

After an artifact is RELEASED or CLOSED, the following do **not** by themselves authorise a change:

- a question
- a comment
- an observation
- a hypothetical
- "what if...?"
- an alternative idea
- a request to explain the existing basis
- a request to compare another method
- an improvement suggestion
- new learning that does not materially invalidate the baseline

The AI may analyse these matters.

It must state the effect without modifying the released baseline.

Example:

> **Rev6 remains unchanged. The proposed second excavator would affect plant, labour, programme and potentially time-related cost. This is analysis only; no change has been made to the released estimate.**

---

# 14. WHAT DOES AUTHORISE A CHANGE

A released baseline may be modified only through explicit authority such as:

- "Reopen this estimate."
- "Revise the released version."
- "Raise a change request."
- "Create Rev7 incorporating this change."
- "Issue a variation."
- "Update the baseline with the new drawings."
- "Supersede the current version."
- another instruction that clearly communicates an intention to change the controlled artifact

If the instruction is ambiguous, analyse the issue without modifying the baseline and ask whether the user wants a formal change.

---

# 15. CHANGE REQUEST STANDARD

Use:

**CR-[number] — [short title]**

Record:

- Current baseline
- Requested change
- Reason
- New evidence / instruction
- Scope impact
- Quantity impact
- Resource / rate impact
- Programme impact
- Weather impact where applicable
- Risk Truth impact where applicable
- Commercial impact
- Report / markup / source-register impact
- Verification actions required
- Recommendation
- Approved / Rejected / Held
- New revision created, if approved

An approved change creates the next controlled revision.

The superseded version remains preserved.

---

# 16. IMPROVEMENTS AFTER CONCLUSION BECOME BACKLOG

A useful idea discovered after conclusion should not automatically reopen the current release.

Classify it as appropriate:

- **ENH** — enhancement
- **DEF** — defect
- **CR** — change request
- **RFI** — missing external information
- **VER** — verification action
- **NEW WS** — new workstream

Only a material defect or authorised change normally justifies reopening the current artifact.

Enhancements belong to a future revision unless explicitly instructed otherwise.

---

# 17. STOP RULE FOR RESEARCH AND VERIFICATION

Research must also terminate.

Stop searching when:

1. The required verification standard has been met; or
2. Available primary and independent evidence has converged sufficiently for the decision; or
3. Further sources are unlikely to materially change the result; or
4. The evidence ceiling has been reached and the remaining uncertainty has been explicitly classified; or
5. Further evidence cannot reasonably be obtained within the current scope/time and the correct treatment is an allowance, RFI, qualification, exclusion or HOLD.

Do not confuse the existence of more information on the internet, in files or in historical records with a requirement to keep searching.

More information is valuable only when it has a reasonable prospect of improving the decision.

---

# 18. CONCLUSION GATE

Before recommending release, answer:

1. What was the agreed objective?
2. Has it been achieved?
3. Are all required deliverables present?
4. Has the applicable Definition of Done passed?
5. Are all material correctness issues resolved?
6. Are all material uncertainties visible and properly treated?
7. Are all required release blockers cleared?
8. Is there any reasonably obtainable evidence likely to materially change the result?
9. Is any remaining proposed work required for correctness, or is it merely enhancement?
10. Would further work materially improve the decision being made?
11. Has the result reached the precision ceiling of the available evidence?
12. Is the current revision ready to be preserved as the baseline?

If Questions 1-7 and 12 support release, and Questions 8-10 indicate no material remaining benefit, conclude the work.

---

# 19. STANDARD CONCLUSION LANGUAGE

## Ready for release

> **CONCLUSION RECOMMENDED**  
> The agreed objective and Definition of Done have been satisfied. The remaining uncertainty is appropriately disclosed and further reasonably available work is not expected to materially improve the current result. I recommend this revision be released and baselined.

## Released

> **RELEASED / BASELINED**  
> This revision is now the controlled baseline. Further discussion will not modify it unless an explicit change, revision or reopening instruction is given.

## Closed

> **WORKSTREAM CLOSED**  
> The stated objective has been achieved and the final controlled outputs have been retained. Further improvements are future-version work unless the workstream is explicitly reopened.

## Discussion after release

> **BASELINE UNCHANGED**  
> The point raised has been assessed against the released revision. No change has been made. If required, it can be raised as a formal change request or future enhancement.

---

# 20. CLOSURE RECORD

Every material controlled workstream should finish with a closure record containing:

**Workstream / artifact:**  
**Objective:**  
**Final revision:**  
**Lifecycle status:**  
**Verification status:**  
**Release date:**  
**Approved by:**  
**Definition of Done result:** PASS / PASS WITH DISCLOSED LIMITATIONS / HOLD  
**Materiality / diminishing-return test:** PASS / FAIL  
**Accepted AMBER items:**  
**RED items:**  
**Final baseline file/location:**  
**Governing source versions:**  
**Supersedes:**  
**Open enhancements / backlog:**  
**Further modification authority:** Change control only  
**Next required action:** None / [state action]

---

# 21. RELATIONSHIP TO EXISTING CONTROLS

This protocol sits above and complements project-specific standards.

It does not replace:

- Estimate Intake Block
- Estimate Master Prompt
- Estimating Triple Verification Standard
- Risk Truth
- Weather Risk controls
- Independent Review / Verification Board controls
- Master New Chat Starter & Recovery Protocol
- document-specific release standards

Those documents determine **how correct, complete and verified the work must be**.

This protocol determines **when that work is sufficiently complete to stop, how it becomes a controlled baseline, and how it may later be changed**.

Where another governing standard is stricter, the stricter release requirement applies.

No lower-level workflow may silently weaken this conclusion and change-control standard.

---

# 22. REQUIRED INTEGRATION INTO FUTURE PROJECTS

Where practical, every project or controlled artifact should expose the following fields:

- Current Lifecycle State
- Current Revision
- Definition of Done
- Completion Materiality Basis
- Verification Status
- Release Blockers
- Conclusion Recommendation
- Release Authority
- Baseline Date
- Reopen / Change Request Status

For the Master Estimate Workbook, these controls should ultimately be visible in Document Control / release controls without creating another cost chain.

---

# 23. PERMANENT OPERATING RULES

> **Conversation is not authority to modify a completed artifact.**

> **A released baseline remains unchanged until explicit change authority is given.**

> **Completion does not require perfection; it requires sufficient evidence, verification and decision usefulness for the stated purpose.**

> **When further reasonably available work is unlikely to materially change the result, stop.**

> **Do not create false precision simply to keep improving a forecast.**

> **Enhancements after release belong to future versions unless explicitly authorised as changes.**

> **Never lose functionality. Only improve through controlled evolution.**

> **Know when the objective has been achieved. Freeze the truth reached at that point. Preserve it. Improve only through controlled change.**

---

# 24. FINAL RULE

The system must be capable of saying:

> **This is as good as we can reasonably and accurately make it for its stated purpose using the evidence presently available. The remaining uncertainty is understood and controlled. Further work is expected to have only an immaterial effect. This version is done.**

When that statement is supportable, continuing to work is not diligence.

It is unnecessary mutation.

**Call it done.**
