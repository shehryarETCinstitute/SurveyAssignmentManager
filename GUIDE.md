# Survey Assignment Manager

This tool turns a Raw Weekday workbook into survey assignments. You pick a block, preview the trips, then save. Nothing is written until you press **Save this cut**.

The work stays in the browser session. Download the workbook before you close the page.

## 1. Upload

Drop in the client Excel file.

- A sheet named Raw Weekday becomes the working sheet. Assignment names start blank.
- Pull-out, pull-in, and deadhead stay on the sheet and are left blank.
- If the file also has a Weekday sheet that already has names, open **Other sheets in this workbook** and choose it when you want to continue that work.

**New file** clears the session and lets you upload again.

## 2. The counts at the top

| Count | Meaning |
| --- | --- |
| Trips | Every trip on the working sheet |
| Open regular | Regular trips that still have no assignment |
| Assignments | How many names or numbers you have saved |
| Next number | The number used when the name box is left blank |

## 3. Cut a shift

**Assignment name.** Leave it blank to use the next number (`1`, `2`, `3`). Type a name such as `Aisha 1` when one person rides more than one block. The same name keeps adding to the same person.

**Include garage moves.** Leave this off for a normal shift. Turn it on for express work that should include pull-out, deadhead, and pull-in.

**Start at.** Where the shift begins. The usual choice is Charlotte Transportation Center. `(Any place)` starts at the first open trip on the block.

**Block.** The bus block you are cutting. The list shows how many trips on that block are still open. The day for that block is on the right.

| Color | Meaning |
| --- | --- |
| White | Open, can be assigned |
| Green | In the preview, not saved yet |
| Blue | Already saved |
| Grey | Garage move, left blank |

**Suggest full shift.** Builds one shift on this block, about 6.5 to 9 hours, starting at the place you chose and ending back there. This is the normal numbered assignment.

**Suggest round trip.** Takes only the next out-and-back to that place. Use this for a short piece.

**Suggest next piece.** Appears after the name already has trips. It looks for a block that leaves the place where that person just finished, with enough time to change buses. The piece is one round trip. Press it again, on another block, to keep building the day.

If no block is offered, open **More options** and widen the change-bus window, or tick **Choose any block**.

## 4. Preview

The green card is the cut before it is saved. It shows the length, the clock times, the block, where to report, and the report time (15 minutes before the first trip).

- **Shorter** drops the last trip.
- **Longer** adds the next open trip on this block.
- **Note for the packet** is optional. Use it for a break or a bus change. The note prints on the Word packet. It is not a trip, so it does not go into the Weekday grid.
- **Save this cut** writes the name onto those trips.

Orange lines are warnings. The cut can still be saved. A warning means the shift is shorter or longer than the usual length, it does not end where it started, a garage move inside the shift was left blank, or there is too little or too much time to change buses.

## 5. More options

| Setting | Usual value | What it does |
| --- | --- | --- |
| No shorter than | 6.5 hours | Full shifts shorter than this are warned |
| No longer than | 9 hours | The suggestion stops before it gets longer than this |
| Start after a clock time | Off | Ignores trips that start earlier |
| End by a clock time | Off | Stops the cut at that time |
| Minutes to change buses | 10 to 90 | How long a person may wait between blocks |

## 6. Assignments

The table at the bottom lists every saved name: trips, blocks, times, hours, and notes.

Click a row to put that name back in the box and add another piece.

**Unassign selected assignment** clears that name from every trip on it. Those trips become open again. Tick the row first.

**Undo last save** removes only the cut you just saved.

## 7. Downloads

**Download Weekday workbook** has two sheets:

- **Weekday** is the full grid, including trips that are still open.
- **Made assignments** is only the trips that already have a name.

**Download [name]** is the Word packet for the name in the box. The header has the assignment, report place, report time, blocks, and shift. Notes sit between the trips.

**Prepare all Word packets**, then **Download all packets**, gives one Word file per assignment plus one file with every assignment.

## Two ways to work

**A numbered shift.** Leave the name blank. Choose the block. Press **Suggest full shift**. Shorten or lengthen if needed. Save. The next save becomes the next number.

**A person on several buses.** Type `Aisha 1`. Suggest a round trip on the first block and save. Press **Suggest next piece**, pick the next block, add a note such as `Switch bus` if you need one, and save. Repeat until the day is done.
