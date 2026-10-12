# Takeoff proof, runs 2 and 3 (civil package + structural details + architectural Rev17)

Follows `TAKEOFF_PROOF_RUN1.md`. Same method: a blind AI takeoff from the drawings and reports only, checked by the platform's deterministic checker (`api/ai_takeoff.py`), then scored line by line against the quantities adopted in Rev34E (`engine/tools/score_takeoff.py`).

**Inputs.** Architectural Rev17 (52 pp), civil "2615 EPA Plans rev e" (10 pp), Infrastructure Assessment rev B, Flood Assessment, Roof Valley Capacity, DHC Structural Details 2026-07-07 (17 pp) and the DHC Calculation Package text (via Drive). Not available: the stamped Yodha ESC drawings DWG231/241.
**Stand-in AI.** A Claude sub-agent per run (no API key in the sandbox), told not to open the estimate. Rick's own key will run the same prompts in the platform; results may differ. Each run took about 2 to 2.5 minutes.
**Matching** of AI lines to estimate lines was done by hand and is listed in the table so it can be checked.

| Estimate line | Unit | Rev34E quantity | AI quantity | Error | Band | Proposals (status) |
|---|---|---:|---:|---:|---|---|
| EW01 Site clearance / surface strip within earthworks | m2 | 2,105.00 | 2,105.00 | +0.0% | within 2% | R2-T02 (verified) |
| EW03 Final trim / formation across earthworks area | m2 | 2,105.00 | 2,105.00 | +0.0% | within 2% | R2-T02 (verified) |
| EW02 Bulk fill placement / compaction - current Yodha | m3 | 1,033.00 | 1,033.00 | +0.0% | within 2% | R2-T06 (verified) |
| EW09 Imported / replacement engineered fill | m3 | 923.00 | 923.00 | +0.0% | within 2% | R2-T08 (verified) |
| EW04 Grassed OLFP diversion channel - 300 deep, 500 b | lm | 94.08 | 92.00 | -2.2% | within 10% | R2-T34 (check) |
| PV01+PV04 Internal carpark / driveway co + External concre | m2 | 568.00 | 568.00 | +0.0% | within 2% | R2-T12 (verified) |
| RW01 Keystone retaining wall - principal wall length  | lm | 73.34 | 68.70 | -6.3% | within 10% | R2-T20 (check) |
| RW02 Keystone retaining wall - low wall length contro | lm | 9.59 | 9.90 | +3.2% | within 10% | R2-T21 (check) |
| RW05 Retaining wall drainage: 100mm Novaflo, aggregat | lm | 82.93 | 78.60 | -5.2% | within 10% | R2-T20 (check), R2-T21 (check) |
| EW05 Foundation pad excavation P1-P4 | m3 | 2.19 | 2.19 | +0.0% | within 2% | R3-S01b (check), R3-S02b (check), R3-S03b (check), R3-S04b (check) |
| EW06 PILE2 bored foundation holes 450 dia x 1.2m | ea | 15.00 | 15.00 | +0.0% | within 2% | R3-S08 (check) |
| RW03 PILE1 bridging piles to Keystone over 450mm SW m | ea | 7.00 | 7.00 | +0.0% | within 2% | R3-S05 (check) |
| PV05 note Parking spaces (21 incl. 1 accessible, stated in | ea | 21.00 | 22.00 | +4.8% | within 10% | R2-T37 (check) |

Scored lines: 13 of 15 quantity lines in the estimate. within 10%: 5, within 2%: 8

## Quantity lines in the estimate the AI did not produce (and were not marked out of scope)

- PV02 Hobsonville Road public VX203 vehicle crossing (37.77 m2) - MEASURED - public Hobsonville Road VX203 crossing footprint
- ES03 Allproof level-threshold drainage to flush exterior openings (44.00 lm) - PROVIDED / CALCULATED ORDER QUANTITY - 22 door thresholds x 2.0m channel/grating each per 

## Out of scope for this drawing set

- ESC01: fence 226.3 lm is from the stamped Yodha ESC drawings (DWG231/241), which were not in the package supplied; the AI said so


## What the result says
- **13 of the 15 quantity lines in Rev34E were produced; 8 within 2%, the other 5 within 10%.** Nothing the AI produced was more than 6.3% from the adopted figure.
- **Where the numbers were READ (earthworks area, cut/fill, imported fill, 568 m2 concrete):** exact. This is retrieval from stated figures, not measurement. It is still hours of legwork saved.
- **Where numbers were COUNTED or CALCULATED from the structural set (17 pads and their 2.19 m3, 15 PILE2, 7 PILE1):** exact. The AI took pad sizes from the S101 schedule, counted the labels on the plan, and the platform did the multiplication.
- **Where numbers were SCALED off the image (retaining wall lengths, OLFP channel, parking count):** 2% to 6% out, every one marked "check" by the platform so the estimator confirms it on the drawing. Rev34E's own retaining lengths are "preliminary plan measurement", so the 'truth' there is itself soft.
- **Conflicts were shown, not resolved.** Rev17 says fill 1,310 m3, the Infrastructure Assessment says 1,033 m3 (the one Rev34E adopted). The AI proposed both as separate lines with the sheets cited. It also flagged tank volume 20.58 m3 (dimensions) versus 18.2 m3 (report), crossing count 1 (civil) versus 2 (architectural), and 14 versus 15 PILE2 labels.
- **Honest limits it stated:** no ESC plan or silt fence length (Appendix 4 not supplied), no topsoil depth, no private drainage lengths, no services trench length.
- **Missed:** the VX203 crossing area (AI gave the 5.5 m width and the count but not the 37.8 m2 footprint) and the 44 lm of threshold channel (22 door thresholds x 2.0 m: the door schedule is in the architectural set; the AI did not look for it).
- **Checker results:** run 2 had 41 lines (15 verified, 24 check, 2 unverified); run 3 had 21 lines (1 verified, 20 check). The checker caught real faults: a "1" that was not in its quote, and a stand-in using an unknown source label for pi, which led to adding a pi / pi/4 "constant" source (nothing else may be a constant).

## Cautions before trusting this
- Small sample: 15 quantity lines, one project, one set of drawings.
- Rev34E is not a surveyed truth. It is what Rick adopted, built by ChatGPT from the same documents, so agreement between two AIs on the same documents is partly expected.
- Many exact matches are retrieved numbers. The real test of measuring is the scaled items (2% to 6% out) and the counts.
- The stand-in is a Claude model. Another provider's model should be scored the same way.
- Not tested: a project with no prior estimate to compare against; drawings that are scanned images with no text layer.

## Next
1. Run the same prompts in the platform with Rick's key (a "Takeoff" page: pick drawings, run, proposals with sheet, page and quote, accept into the QS draft).
2. Verification and marked-up drawings: click a proposal, see the page, highlight the source region, export an annotated PDF.
3. Door schedule / count items and the area-from-polygon items, which the AI skipped.
