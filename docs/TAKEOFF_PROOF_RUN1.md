# Takeoff proof, run 1 (Hobsonville, architectural Rev17 only)

**What this is.** A first, small, honest test of "can the AI take quantities off the drawings and how close does it get to what was finally adopted in Rev34E".
**Stand-in AI.** No API key exists in the build sandbox, so the blind run was done by a Claude sub-agent given only the Rev17 page images and page text (it was told not to open the estimate). Rick's own Anthropic key will run the same prompt in the platform; results may differ.
**Only one drawing set.** Only the Architectural Rev17 consent set (52 pages) was available. The civil (DWG301/311/331, Yodha ESC DWG231/241), structural (DHC S101/S303/S304) and flood/infrastructure reports are on Rick's Drive but were not available in the sandbox. Seven Rev34E quantity lines can only come from those, so they are listed as out of scope, not failures.
**Truth is not perfect.** Rev34E quantities are what Rick adopted (all AMBER), not a surveyed truth; RW01/RW02 are marked "preliminary plan measurement".
**Speed.** The sub-agent produced 27 proposed lines in about 2 minutes (10 tool calls). The platform read all 52 pages' text in 1.4 seconds (pypdfium2).

| Estimate line | Unit | Rev34E quantity | AI quantity | Error | Band | Proposals (status) |
|---|---|---:|---:|---:|---|---|
| EW01 Site clearance / surface strip within earthworks | m2 | 2,105.00 | 2,105.00 | +0.0% | within 2% | T07 (verified) |
| EW03 Final trim / formation across earthworks area | m2 | 2,105.00 | 2,105.00 | +0.0% | within 2% | T07 (verified) |
| PV01+PV04 Internal carpark / driveway co + External concre | m2 | 568.00 | 568.00 | +0.0% | within 2% | T01 (verified) |
| EW02 Bulk fill placement / compaction - current Yodha | m3 | 1,033.00 | 1,310.00 | +26.8% | outside 25% | T04 (verified) |
| RW01 Keystone retaining wall - principal wall length  | lm | 73.34 | 69.70 | -5.0% | within 10% | T08 (check) |
| RW02 Keystone retaining wall - low wall length contro | lm | 9.59 | 10.90 | +13.7% | within 25% | T09 (check) |
| RW05 Retaining wall drainage: 100mm Novaflo, aggregat | lm | 82.93 | 80.60 | -2.8% | within 10% | T08 (check), T09 (check) |
| PV05 note Parking spaces (21 incl. 1 accessible, stated in | ea | 21.00 | 22.00 | +4.8% | within 10% | T17 (check) |

Scored lines: 8 of 15 quantity lines in the estimate. outside 25%: 1, within 10%: 3, within 2%: 3, within 25%: 1

## Out of scope for this drawing set

- EW04: OLFP channel length comes from the Yodha flood assessment and a civil alignment, not the architectural set
- EW05: foundation pads are on structural sheet S101 (not in this set)
- EW06: 15 PILE2 confirmed by the subcontractor against structural Rev B
- EW09: net imported fill is from the Yodha RevB mass balance
- PV02: VX203 crossing area is from civil DWG301/331 (AI counted the crossing but gave no area)
- ES03: 22 door thresholds x 2.0 m: needs the door schedule count (AI said no threshold lengths in this set)
- RW03: 7 PILE1 on structural S101/S304
- ESC01: fence 226.3 lm is from the stamped Yodha ESC drawings DWG231/241
- RH01: n/a

## AI lines with no matching estimate line (extra, to be reviewed)

- T02 Front-yard driveway area (subset of site impervious, information) - 69.45 m2 (verified)
- T03 Approx earthworks - fill (area) - 1635.0 m2 (verified)
- T05 Approx earthworks - cut (area) - 470.0 m2 (verified)
- T06 Approx earthworks - cut (volume) - 113.0 m3 (verified)
- T10 Dish channels to carpark (concrete, Proposed dish channel to Cp) total - 51.5 lm (check)
- T11 Type 1 cesspits - 2.0 ea (check)
- T12 Type 2 cesspits - 2.0 ea (check)
- T13 New stormwater manhole (New SWMH) - 1.0 ea (check)
- T14 Existing 450 dia stormwater line to be removed - manholes/cesspit removals (existing manhole, cesspit) - 2.0 ea (check)
- T15 Proposed new vehicle crossing - 1.0 ea (check)
- T16 Existing vehicle crossings (remove) - 2.0 ea (check)
- T18 Temporary 2.0m chainlink site fence (entire work area) - 1.0 LS (unverified)
- T19 Permanent fence 1 (2.0m acoustic) - north boundary, taken as boundary length - 30.03 lm (verified)
- T20 Permanent fence 2 (1.8m acoustic) - west boundary - 65.65 lm (verified)
- T21 Permanent fence 3 (1.5m acoustic) - south boundary west portion - 15.43 lm (verified)
- T22 Concrete landing at entry - 4.5 m2 (verified)
- T23 Portico slab level with FFL - 14.65 m2 (verified)
- T24 Concrete pads (A/C units / eng. pads) - 2.0 ea (check)
- T25 Timber decks (external) - 158.0 m2 (verified)
- T26 Outdoor play areas (surface finish not stated) - 780.0 m2 (verified)
- T27 APD detention tank (volume of tank) - 20.581458 m3 (verified)

## Reading the result
- **Read from the drawing text (stated figures): exact.** Earthworks area 2,105 m2 (EW01, EW03) and the 568 m2 concrete total (PV01+PV04) were written on the A1 site plan and the AI quoted them. The platform confirmed every quote is on the cited page. This is retrieval rather than measurement, but it is exactly the legwork that takes a person time.
- **Conflict surfaced, not resolved.** Rev17 says fill 1,310 m3; Rev34E adopted 1,033 m3 from the Yodha report (a RED conflict in Rev34E). The AI read Rev17 correctly. The adopted number came from a different document, which is why the AI is 26.8% "out".
- **Scaled from the image: 3% to 14% out** (retaining wall lengths, low confidence, marked "check" by the platform). Usable as a first pass that the estimator verifies; not usable unchecked.
- **Counted: 22 vs 21 bays.** The AI counted 22 numbered bays; the estimate's note says 21 incl. 1 accessible.
- **Not measurable from this set** (the AI said so rather than guessing): earthworks surfaces, pavement build-ups, drainage pipe lengths, threshold drain lengths, ESC layout, pile and footing counts.
- **Platform checks worked.** 15 lines verified (every number found on its page), 11 flagged "check" (scaled or counted), 1 rejected (a "1" not in its quote).
- **Extra lines** (decks, play areas, cesspits, crossings, boundary fences, detention tank) are things a person might want; none have a Rev34E counterpart in the siteworks package.

## What this does not prove yet
Whether the AI can measure from civil drawings (long pipe runs, areas by polygon, cut/fill). That needs the civil and structural PDFs and is the test that matters.
