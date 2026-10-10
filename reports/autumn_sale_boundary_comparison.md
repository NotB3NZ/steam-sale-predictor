# Autumn Sale Boundary Comparison — Phase 5A.1

Original Phase 5A commit: `509377ca2a217b1d908add07814a49928a55fe08`. Baseline directory: `reports/baselines/phase_5a_calendar_window/`. Original 200 pairs and 238 records were verified before the exact-window audit.

The old UTC calendar windows started at midnight and ended at midnight after the last sale date. Corrected windows use verified Valve event hours and include start, exclude end. Only directly timestamped records contribute; no states are carried forward.

| Year | Original A/B/C/D | Exact A/B/C/D | Category changes | Original records | Exact records | Removed before start | Removed at/after end | Added | Affected original B |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023 | 55/8/0/37 | 55/2/0/43 | 6 | 118 | 57 | 1 | 60 | 0 | 6 |
| 2024 | 60/4/0/36 | 60/0/0/40 | 4 | 120 | 60 | 0 | 60 | 0 | 4 |

2025 is new audit scope and has no original baseline. 2026 is excluded. The exact 2023/2024 windows lie entirely inside their original calendar windows, so additions are not expected; the comparison computes them rather than assuming zero.

## Each category change

| Year | AppID | Name | Original | Exact | Original count | Exact count | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2024 | 7830 | Men of War™ | B | D | 1 | 0 | at_or_after_exact_sale_end |
| 2023 | 303680 | FATE: The Traitor Soul | B | D | 1 | 0 | at_or_after_exact_sale_end |
| 2023 | 1158850 | The Great Ace Attorney Chronicles | B | D | 1 | 0 | at_or_after_exact_sale_end |
| 2024 | 1239260 | Barro F | B | D | 1 | 0 | at_or_after_exact_sale_end |
| 2024 | 1257270 | The Valley of Super Flowers | B | D | 1 | 0 | at_or_after_exact_sale_end |
| 2023 | 1836120 | QUICKERFLAK | B | D | 1 | 0 | at_or_after_exact_sale_end |
| 2023 | 1882420 | Learn Programming: Python - Remake | B | D | 1 | 0 | at_or_after_exact_sale_end |
| 2023 | 2383710 | Caveman Ransom | B | D | 1 | 0 | at_or_after_exact_sale_end |
| 2023 | 2621900 | Railway Islands 2 - Puzzle | B | D | 1 | 0 | at_or_after_exact_sale_end |
| 2024 | 2650840 | nekowater | B | D | 1 | 0 | at_or_after_exact_sale_end |

## Every original category B case

The original B cases each had one full-price observation. The table shows that observation and its actual relationship to the exact event; retained B and new D remain evidence descriptions, not negative labels.

| Year | AppID | Name | UTC timestamp | Price | Regular | Cut | Exact category | Boundary result |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024 | 7830 | Men of War™ | 2024-12-04T18:17:52Z | 4.99 | 4.99 | 0 | D | at_or_after_exact_sale_end |
| 2023 | 303680 | FATE: The Traitor Soul | 2023-11-28T18:13:59Z | 7.99 | 7.99 | 0 | D | at_or_after_exact_sale_end |
| 2023 | 1158850 | The Great Ace Attorney Chronicles | 2023-11-28T20:12:20Z | 39.99 | 39.99 | 0 | D | at_or_after_exact_sale_end |
| 2024 | 1239260 | Barro F | 2024-12-04T18:48:03Z | 4.99 | 4.99 | 0 | D | at_or_after_exact_sale_end |
| 2024 | 1257270 | The Valley of Super Flowers | 2024-12-04T18:48:03Z | 4.99 | 4.99 | 0 | D | at_or_after_exact_sale_end |
| 2023 | 1836120 | QUICKERFLAK | 2023-11-28T21:06:13Z | 0.99 | 0.99 | 0 | D | at_or_after_exact_sale_end |
| 2023 | 1882420 | Learn Programming: Python - Remake | 2023-11-28T21:10:19Z | 2.99 | 2.99 | 0 | D | at_or_after_exact_sale_end |
| 2023 | 2268470 | HOPE LEFT ME | 2023-11-25T18:24:20Z | 1.99 | 1.99 | 0 | B | retained_inside_exact_window |
| 2023 | 2383710 | Caveman Ransom | 2023-11-28T21:39:53Z | 4.99 | 4.99 | 0 | D | at_or_after_exact_sale_end |
| 2023 | 2621900 | Railway Islands 2 - Puzzle | 2023-11-28T21:47:40Z | 3.99 | 3.99 | 0 | D | at_or_after_exact_sale_end |
| 2023 | 2650840 | nekowater | 2023-11-21T22:39:17Z | 2.99 | 2.99 | 0 | B | retained_inside_exact_window |
| 2024 | 2650840 | nekowater | 2024-12-04T18:35:54Z | 1.99 | 1.99 | 0 | D | at_or_after_exact_sale_end |

## Start and end boundary effects on every affected pair

Effects include record changes that leave the category unchanged, such as A remaining A after a post-sale full-price observation is removed. Removed records remain in the baseline and can become contextual before/after evidence; they do not contribute to an in-window category.

| Year | AppID | Name | Original → exact | Original count | Exact count | Start removals | End removals | Added |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024 | 7830 | Men of War™ | B → D | 1 | 0 | 0 | 1 | 0 |
| 2023 | 9730 | Tycoon City: New York | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 9730 | Tycoon City: New York | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 15170 | Heroes of Might & Magic V | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 15170 | Heroes of Might & Magic V | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 20710 | Mr. Robot | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 38210 | Roogoo | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 38210 | Roogoo | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 61600 | Zen Bound 2 | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 61600 | Zen Bound 2 | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 115320 | Prototype 2 | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 115320 | Prototype 2 | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 213670 | South Park™: The Stick of Truth™ | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 213670 | South Park™: The Stick of Truth™ | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 218740 | Pid | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 218740 | Pid | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 219200 | Droid Assault | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 219200 | Droid Assault | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 234490 | Rush Bros. | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 234490 | Rush Bros. | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 242960 | Blood Omen 2: Legacy of Kain | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 252490 | Rust | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 252490 | Rust | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 262470 | Rollers of the Realm | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 262470 | Rollers of the Realm | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 270880 | American Truck Simulator | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 292400 | Unrest | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 292400 | Unrest | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 303680 | FATE: The Traitor Soul | B → D | 1 | 0 | 0 | 1 | 0 |
| 2023 | 312520 | Rain World | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 312520 | Rain World | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 331200 | Grass Simulator | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 331200 | Grass Simulator | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 360430 | Mafia III: Definitive Edition | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 360430 | Mafia III: Definitive Edition | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 363890 | RPG Maker MV | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 363890 | RPG Maker MV | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 397310 | Looterkings | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 418030 | Subsistence | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 418030 | Subsistence | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 445220 | Avorion | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 445220 | Avorion | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 528950 | Nekuia | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 528950 | Nekuia | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 536220 | The Walking Dead: A New Frontier | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 536220 | The Walking Dead: A New Frontier | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 582660 | Black Desert | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 582660 | Black Desert | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 595140 | Immortal Redneck | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 700600 | Evil Genius 2: World Domination | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 700600 | Evil Genius 2: World Domination | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 708430 | Kamikaze Cube | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 708430 | Kamikaze Cube | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 757320 | Atomicrops | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 757320 | Atomicrops | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 791800 | Mind Over Mushroom | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 799600 | Cosmoteer: Starship Architect & Commander | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 799600 | Cosmoteer: Starship Architect & Commander | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 809230 | Unity of Command II | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 809230 | Unity of Command II | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 821720 | 20.000 Leagues Under The Sea - Captain Nemo | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 826420 | Dark Romance: Heart of the Beast Collector's Edition | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 826420 | Dark Romance: Heart of the Beast Collector's Edition | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 829590 | CryoFall | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 887920 | Maestro: Music from the Void Collector's Edition | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 887920 | Maestro: Music from the Void Collector's Edition | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 965590 | Sagrada | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 1083210 | 符文女孩/Rune Girl | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 1083210 | 符文女孩/Rune Girl | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 1090250 | Crunch Element | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 1158850 | The Great Ace Attorney Chronicles | B → D | 1 | 0 | 0 | 1 | 0 |
| 2024 | 1158850 | The Great Ace Attorney Chronicles | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 1239260 | Barro F | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 1239260 | Barro F | B → D | 1 | 0 | 0 | 1 | 0 |
| 2023 | 1249680 | Ninshi Masuta | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 1249680 | Ninshi Masuta | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 1257270 | The Valley of Super Flowers | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 1257270 | The Valley of Super Flowers | B → D | 1 | 0 | 0 | 1 | 0 |
| 2023 | 1373180 | The Sea Hotel☆Umineko Tei | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 1373180 | The Sea Hotel☆Umineko Tei | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 1413660 | Elderand | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 1418360 | Lonesome Village | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 1418360 | Lonesome Village | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 1465260 | Cyberpunk SFX | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 1532510 | Purrfect Apawcalypse: Love at Furst Bite | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 1532510 | Purrfect Apawcalypse: Love at Furst Bite | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 1560770 | Tower of Waifus 2 | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 1560770 | Tower of Waifus 2 | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 1588760 | Switchball HD | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 1588760 | Switchball HD | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 1655440 | Themes of Dark and Light | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 1740720 | Have a Nice Death | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 1785150 | Friends vs Friends | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 1785150 | Friends vs Friends | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 1836120 | QUICKERFLAK | B → D | 1 | 0 | 0 | 1 | 0 |
| 2024 | 1836120 | QUICKERFLAK | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 1882420 | Learn Programming: Python - Remake | B → D | 1 | 0 | 0 | 1 | 0 |
| 2024 | 1882420 | Learn Programming: Python - Remake | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 2009420 | Zaxterion: Space Frenzy! | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 2009420 | Zaxterion: Space Frenzy! | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 2123430 | BULLCRAP! | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 2205710 | Hentai Beauty | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 2205710 | Hentai Beauty | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 2265760 | Chosun Zombie Defense | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 2270520 | No Way Out | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 2270520 | No Way Out | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 2312170 | pWordle | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 2314050 | Waifu Space Conquest | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 2314050 | Waifu Space Conquest | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 2383710 | Caveman Ransom | B → D | 1 | 0 | 0 | 1 | 0 |
| 2024 | 2383710 | Caveman Ransom | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 2387820 | Beach Gas Gas | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 2387820 | Beach Gas Gas | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 2490910 | 富甲天下5 | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 2490910 | 富甲天下5 | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 2544720 | Workplace Fantasy | A → A | 3 | 1 | 1 | 1 | 0 |
| 2024 | 2544720 | Workplace Fantasy | A → A | 2 | 1 | 0 | 1 | 0 |
| 2023 | 2621900 | Railway Islands 2 - Puzzle | B → D | 1 | 0 | 0 | 1 | 0 |
| 2024 | 2621900 | Railway Islands 2 - Puzzle | A → A | 2 | 1 | 0 | 1 | 0 |
| 2024 | 2650840 | nekowater | B → D | 1 | 0 | 0 | 1 | 0 |

## Every removed record

| Year | AppID | Name | Raw index | UTC timestamp | Price | Regular | Cut | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023 | 9730 | Tycoon City: New York | 53 | 2023-11-28T18:12:21Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 15170 | Heroes of Might & Magic V | 49 | 2023-11-28T18:18:20Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 20710 | Mr. Robot | 18 | 2023-11-28T18:12:25Z | 7.99 | 7.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 38210 | Roogoo | 43 | 2023-11-28T19:06:29Z | 3.99 | 3.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 61600 | Zen Bound 2 | 21 | 2023-11-28T18:30:29Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 115320 | Prototype 2 | 49 | 2023-11-28T18:12:51Z | 39.99 | 39.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 213670 | South Park™: The Stick of Truth™ | 57 | 2023-11-28T18:36:43Z | 29.99 | 29.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 218740 | Pid | 29 | 2023-11-28T22:26:21Z | 19.99 | 19.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 219200 | Droid Assault | 37 | 2023-11-28T18:48:58Z | 12.99 | 12.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 234490 | Rush Bros. | 25 | 2023-11-28T18:13:13Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 242960 | Blood Omen 2: Legacy of Kain | 39 | 2023-11-28T18:19:04Z | 6.99 | 6.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 252490 | Rust | 52 | 2023-11-28T18:25:29Z | 39.99 | 39.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 262470 | Rollers of the Realm | 18 | 2023-11-28T18:43:08Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 270880 | American Truck Simulator | 63 | 2023-11-28T18:25:45Z | 19.99 | 19.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 292400 | Unrest | 23 | 2023-11-28T18:25:58Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 303680 | FATE: The Traitor Soul | 21 | 2023-11-28T18:13:59Z | 7.99 | 7.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 312520 | Rain World | 59 | 2023-11-28T18:19:50Z | 24.99 | 24.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 331200 | Grass Simulator | 33 | 2023-11-28T18:07:26Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 360430 | Mafia III: Definitive Edition | 57 | 2023-11-28T18:50:38Z | 29.99 | 29.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 363890 | RPG Maker MV | 58 | 2023-11-28T18:14:41Z | 79.99 | 79.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 397310 | Looterkings | 54 | 2023-11-28T18:14:59Z | 17.99 | 17.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 418030 | Subsistence | 67 | 2023-11-28T18:07:54Z | 13.99 | 13.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 445220 | Avorion | 29 | 2023-11-28T18:21:21Z | 24.99 | 24.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 528950 | Nekuia | 65 | 2023-11-28T18:22:22Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 536220 | The Walking Dead: A New Frontier | 50 | 2023-11-28T18:40:01Z | 14.99 | 14.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 582660 | Black Desert | 40 | 2023-11-28T19:04:55Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 700600 | Evil Genius 2: World Domination | 29 | 2023-11-28T22:30:16Z | 39.99 | 39.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 708430 | Kamikaze Cube | 67 | 2023-11-28T19:38:50Z | 0.99 | 0.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 757320 | Atomicrops | 65 | 2023-11-28T19:42:59Z | 14.99 | 14.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 799600 | Cosmoteer: Starship Architect & Commander | 57 | 2023-11-28T19:45:22Z | 19.99 | 19.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 809230 | Unity of Command II | 57 | 2023-11-28T19:45:55Z | 29.99 | 29.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 826420 | Dark Romance: Heart of the Beast Collector's Edition | 24 | 2023-11-28T19:46:53Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 829590 | CryoFall | 59 | 2023-11-28T19:48:12Z | 19.99 | 19.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 887920 | Maestro: Music from the Void Collector's Edition | 22 | 2023-11-28T19:51:27Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1083210 | 符文女孩/Rune Girl | 65 | 2023-11-28T20:06:43Z | 0.99 | 0.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1090250 | Crunch Element | 14 | 2023-11-28T22:40:00Z | 19.99 | 19.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1158850 | The Great Ace Attorney Chronicles | 51 | 2023-11-28T20:12:20Z | 39.99 | 39.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1239260 | Barro F | 55 | 2023-11-28T20:18:44Z | 0.99 | 0.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1249680 | Ninshi Masuta | 33 | 2023-11-28T20:19:16Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1257270 | The Valley of Super Flowers | 65 | 2023-11-28T20:19:38Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1373180 | The Sea Hotel☆Umineko Tei | 15 | 2023-11-28T20:27:32Z | 6.99 | 6.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1413660 | Elderand | 59 | 2023-11-28T20:30:47Z | 19.99 | 19.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1418360 | Lonesome Village | 65 | 2023-11-28T20:31:02Z | 19.99 | 19.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1465260 | Cyberpunk SFX | 58 | 2023-11-28T20:33:20Z | 11.99 | 11.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1532510 | Purrfect Apawcalypse: Love at Furst Bite | 21 | 2023-11-28T20:38:09Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1560770 | Tower of Waifus 2 | 61 | 2023-11-28T20:39:36Z | 1.99 | 1.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1588760 | Switchball HD | 63 | 2023-11-28T20:43:04Z | 8.99 | 8.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1655440 | Themes of Dark and Light | 16 | 2023-11-28T20:46:14Z | 6.99 | 6.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1785150 | Friends vs Friends | 67 | 2023-11-28T21:03:33Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1836120 | QUICKERFLAK | 48 | 2023-11-28T21:06:13Z | 0.99 | 0.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 1882420 | Learn Programming: Python - Remake | 27 | 2023-11-28T21:10:19Z | 2.99 | 2.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 2009420 | Zaxterion: Space Frenzy! | 40 | 2023-11-28T21:17:56Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 2205710 | Hentai Beauty | 57 | 2023-11-28T21:29:21Z | 0.99 | 0.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 2270520 | No Way Out | 43 | 2023-11-28T21:33:51Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 2314050 | Waifu Space Conquest | 49 | 2023-11-28T21:35:54Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 2383710 | Caveman Ransom | 67 | 2023-11-28T21:39:53Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 2387820 | Beach Gas Gas | 63 | 2023-11-28T21:40:05Z | 99.99 | 99.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 2490910 | 富甲天下5 | 51 | 2023-11-28T21:43:10Z | 7.99 | 7.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 2544720 | Workplace Fantasy | 67 | 2023-11-28T21:46:12Z | 14.99 | 14.99 | 0 | at_or_after_exact_sale_end |
| 2023 | 2544720 | Workplace Fantasy | 69 | 2023-11-21T15:48:33Z | 14.99 | 14.99 | 0 | before_exact_sale_start |
| 2023 | 2621900 | Railway Islands 2 - Puzzle | 61 | 2023-11-28T21:47:40Z | 3.99 | 3.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 7830 | Men of War™ | 24 | 2024-12-04T18:17:52Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 9730 | Tycoon City: New York | 37 | 2024-12-04T18:17:53Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 15170 | Heroes of Might & Magic V | 31 | 2024-12-04T18:17:53Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 38210 | Roogoo | 29 | 2024-12-04T18:17:56Z | 3.99 | 3.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 61600 | Zen Bound 2 | 13 | 2024-12-04T18:17:58Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 115320 | Prototype 2 | 31 | 2024-12-04T18:18:00Z | 39.99 | 39.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 213670 | South Park™: The Stick of Truth™ | 39 | 2024-12-04T18:18:03Z | 29.99 | 29.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 218740 | Pid | 21 | 2024-12-04T18:18:04Z | 19.99 | 19.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 219200 | Droid Assault | 24 | 2024-12-04T19:36:13Z | 12.99 | 12.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 234490 | Rush Bros. | 17 | 2024-12-04T18:18:07Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 252490 | Rust | 33 | 2024-12-04T18:18:11Z | 39.99 | 39.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 262470 | Rollers of the Realm | 10 | 2024-12-04T18:18:13Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 292400 | Unrest | 15 | 2024-12-04T18:18:20Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 312520 | Rain World | 39 | 2024-12-04T18:18:25Z | 24.99 | 24.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 331200 | Grass Simulator | 25 | 2024-12-04T18:18:32Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 360430 | Mafia III: Definitive Edition | 37 | 2024-12-04T18:24:06Z | 29.99 | 29.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 363890 | RPG Maker MV | 38 | 2024-12-04T18:24:07Z | 79.99 | 79.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 418030 | Subsistence | 45 | 2024-12-04T18:24:25Z | 13.99 | 13.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 445220 | Avorion | 17 | 2024-12-04T18:24:33Z | 24.99 | 24.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 528950 | Nekuia | 43 | 2024-12-04T18:29:37Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 536220 | The Walking Dead: A New Frontier | 32 | 2024-12-04T18:29:41Z | 14.99 | 14.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 582660 | Black Desert | 26 | 2024-12-04T18:29:53Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 595140 | Immortal Redneck | 15 | 2024-12-04T18:29:56Z | 19.95 | 19.95 | 0 | at_or_after_exact_sale_end |
| 2024 | 700600 | Evil Genius 2: World Domination | 19 | 2024-12-04T18:30:24Z | 39.99 | 39.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 708430 | Kamikaze Cube | 43 | 2024-12-04T18:29:40Z | 0.99 | 0.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 757320 | Atomicrops | 41 | 2024-12-04T18:36:09Z | 14.99 | 14.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 791800 | Mind Over Mushroom | 13 | 2024-12-04T18:36:18Z | 14.99 | 14.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 799600 | Cosmoteer: Starship Architect & Commander | 35 | 2024-12-04T18:36:20Z | 19.99 | 19.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 809230 | Unity of Command II | 37 | 2024-12-04T18:36:22Z | 29.99 | 29.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 821720 | 20.000 Leagues Under The Sea - Captain Nemo | 41 | 2024-12-04T18:36:25Z | 1.99 | 1.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 826420 | Dark Romance: Heart of the Beast Collector's Edition | 18 | 2024-12-04T18:36:26Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 887920 | Maestro: Music from the Void Collector's Edition | 16 | 2024-12-04T18:36:41Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 965590 | Sagrada | 40 | 2024-12-04T18:42:15Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 1083210 | 符文女孩/Rune Girl | 41 | 2024-12-04T18:42:31Z | 0.99 | 0.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 1158850 | The Great Ace Attorney Chronicles | 33 | 2024-12-04T18:48:22Z | 39.99 | 39.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 1239260 | Barro F | 33 | 2024-12-04T18:48:03Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 1249680 | Ninshi Masuta | 21 | 2024-12-04T18:48:42Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 1257270 | The Valley of Super Flowers | 43 | 2024-12-04T18:48:03Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 1373180 | The Sea Hotel☆Umineko Tei | 9 | 2024-12-04T19:36:22Z | 6.99 | 6.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 1418360 | Lonesome Village | 41 | 2024-12-04T18:54:37Z | 19.99 | 19.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 1532510 | Purrfect Apawcalypse: Love at Furst Bite | 13 | 2024-12-04T19:00:11Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 1560770 | Tower of Waifus 2 | 39 | 2024-12-04T19:00:19Z | 1.99 | 1.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 1588760 | Switchball HD | 41 | 2024-12-04T19:00:29Z | 8.99 | 8.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 1740720 | Have a Nice Death | 29 | 2024-12-04T19:06:19Z | 24.99 | 24.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 1785150 | Friends vs Friends | 45 | 2024-12-04T19:05:41Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 1836120 | QUICKERFLAK | 28 | 2024-12-04T19:11:46Z | 0.99 | 0.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 1882420 | Learn Programming: Python - Remake | 17 | 2024-12-04T19:11:58Z | 2.99 | 2.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 2009420 | Zaxterion: Space Frenzy! | 20 | 2024-12-04T19:18:05Z | 9.99 | 9.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 2123430 | BULLCRAP! | 4 | 2024-12-04T19:18:23Z | 5.99 | 5.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 2205710 | Hentai Beauty | 37 | 2024-12-04T19:23:49Z | 0.99 | 0.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 2265760 | Chosun Zombie Defense | 16 | 2024-12-04T19:24:02Z | 18.99 | 18.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 2270520 | No Way Out | 21 | 2024-12-04T19:24:03Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 2312170 | pWordle | 15 | 2024-12-04T19:24:11Z | 2.99 | 2.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 2314050 | Waifu Space Conquest | 35 | 2024-12-04T19:24:12Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 2383710 | Caveman Ransom | 43 | 2024-12-04T19:23:41Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 2387820 | Beach Gas Gas | 43 | 2024-12-04T19:23:43Z | 99.99 | 99.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 2490910 | 富甲天下5 | 31 | 2024-12-04T19:29:36Z | 7.99 | 7.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 2544720 | Workplace Fantasy | 44 | 2024-12-04T19:29:45Z | 13.99 | 13.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 2621900 | Railway Islands 2 - Puzzle | 38 | 2024-12-04T19:29:19Z | 4.99 | 4.99 | 0 | at_or_after_exact_sale_end |
| 2024 | 2650840 | nekowater | 35 | 2024-12-04T18:35:54Z | 1.99 | 1.99 | 0 | at_or_after_exact_sale_end |

## Newly included records

None.

## Original artifact SHA-256

| Original relative path | Preserved SHA-256 |
| --- | --- |
| data/intermediate/autumn_sale_evidence_audit.csv | 2b3966281bfcee412f3fc711784e812422c2588db63f3deedebad07a93798c45 |
| data/intermediate/autumn_sale_evidence_records.csv | 8ad9c5e3fd943ca6d007efbfcf8450731c4ab771cb6e0ee850f51bae19d1ed4a |
| reports/autumn_sale_evidence_audit.md | 0c4f9b6d0d116afed61a1cba3c2ac45987bd3939d8935a50b927e6c7b41141d7 |
| reports/autumn_sale_evidence_validation.json | ab2fc459327f23ac4d9150a9f04168cde9e4ce5ae27d98d68ceb384d91af6e42 |
| src/04_audit_autumn_evidence.py | f0efe57cb8ef4c4171ba7a57c7ba31ad78c7003c743c5765e07fc07328c1b37c |
| PROJECT_CONTEXT.md | cc36fe0cd39bce938cdc04d453959c469c19a41ec34407e33dbbb29abc21f286 |

Validation reconciles original records − removed + added = corrected records for each year. Shared records retain identical raw JSON; original raw array indices identify records without deduplicating timestamps. The baseline hashes and Phase 4 hashes remain unchanged before/after execution.

**Stopped after Phase 5A.1. Coverage sufficiency, state persistence, and final labeling remain Phase 5B decisions.**
