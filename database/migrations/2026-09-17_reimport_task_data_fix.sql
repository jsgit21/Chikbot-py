-- Reimport the real Major/Minor task data from tasks-2026-final.xlsx.
-- Supersedes 2026-09-17_reimport_task_data.sql, which cannot run on any
-- schema: its `truncate table task;` is blocked by the FK from
-- team_minor_history.minor_task_id to task(id) (added in
-- 2026-09-15_task_and_minor_history.sql) -- InnoDB refuses TRUNCATE on a
-- table any FK still references, regardless of the referencing table's row
-- count. That file is left unrun and unedited per the no-edit-after-merge
-- migration rule; this file replaces it entirely.
--
-- 114 Majors (tile_sequence 1..114, board order from the "Export" sheet)
-- and 100 Minors (shared pool, tile_sequence null). Major #60, "Yama is
-- blocking the path! What will you do?", is the doomsday tile (moved from
-- #58; the two "Moons of Peril" Majors that used to be #59/#60 shift up to
-- #58/#59).
--
-- Run against BOTH schemas, e.g.:
--   mysql candyland      < 2026-09-17_reimport_task_data_fix.sql
--   mysql candyland_test < 2026-09-17_reimport_task_data_fix.sql
--
-- team_minor_history is cleared unconditionally on both schemas, not just
-- candyland_test: once task is reimported, any existing
-- team_minor_history.minor_task_id values point at rows that no longer
-- exist, so the clear is a correctness requirement here, not a test-only
-- workaround. DELETE is used instead of TRUNCATE so the FK from
-- team_minor_history doesn't block the following delete from task (DELETE
-- only fails on a live reference, and team_minor_history is empty by the
-- time task is cleared). auto_increment is reset explicitly since DELETE,
-- unlike TRUNCATE, doesn't reset it on its own.

delete from team_minor_history;
delete from task;
alter table task auto_increment = 1;

-- Majors
insert into task (kind, tile_sequence, title, task, notes) values
  ('major', 1, 'Huey Mass Event', 'Obtain 6 Hueycoatl hides.', 'All teams play MUST play together on **W495** in one mass lobby. You can only split into smaller groups after the first Hueycoatl hide drop!'),
  ('major', 2, 'It''s time for Castle Wars.', 'Your entire team must Green Log the Castle Wars collection log.', 'You''ll understand this if you watched the technical demo and know how /candyland roll works.'),
  ('major', 3, 'The Fractured Archive: Team tryouts', 'Complete each raid 1 time.', 'If a team has multiple inexperienced players, these are allowed: Entry mode Theatre of Blood, Entry mode Tombs of Amascut'),
  ('major', 4, 'Welp... we''re boned', 'Obtain 2 Bone Sceptre''s and 2 scurrius spines.', null),
  ('major', 5, 'A Royal Tribute', 'Obtain 1 of the following Royal Titans uniques: Fire Element Staff Crown, Ice Element Staff Crown, Deadeye prayer scroll, Mystic Vigour prayer scroll, Pet', 'This does not include: Giantsoul amulet, Dessicated pages'),
  ('major', 6, 'Why is that cow in a pool?', 'Obtain the Beef pet.', null),
  ('major', 7, 'Sacrifice an Ultimate Ironman', 'Obtain any Zulrah unique.', 'This does not include: Zul-andra teleport, Zulrah''s scales'),
  ('major', 8, 'Momma needs a new handbag', 'Obtain the Immaculate Mole skin and the Pristine Spider silk.', 'Don''t worry, it''s possible to obtain these after already getting them.'),
  ('major', 9, 'Being a hero sometimes requires stealing...', 'Fill a Stash Unit: Fountain of Heroes (Elite)', 'All items must be dropped by an npc, or crafted through raw materials you obtain. Items required: Dragon boots, Splitbark legs, Rune longsword'),
  ('major', 10, 'Things are heating up!', 'Obtain the Fire Element Staff Crown from Branda.', 'Everyone targets Branda!'),
  ('major', 11, 'OMG who turned on the air conditioning!!', 'Obtain the Ice Element Staff Crown from Eldric.', 'Everyone targets Eldric!'),
  ('major', 12, 'Wake up! Grab a brush and put on a little makeup!', 'Obtain 2 Awakener''s orbs.', 'Player''s choice.'),
  ('major', 13, 'A Song of Ice and Fire', 'Obtain the Pet OR both of the Ice and Fire Element Staff Crown pieces.', 'Split your team between Fire and Ice, or tackle one at a a time!'),
  ('major', 14, 'The Fractured Archive: Team tryouts', 'Complete each raid 1 time.', 'If a team has multiple inexperienced players, these are allowed: Entry mode Theatre of Blood, Entry mode Tombs of Amascut'),
  ('major', 15, 'Babe... I want to go ring shopping!!', 'Obtain any 2 rings from the Dagganoth Kings.', 'Duplicates are allowed on THIS tile.'),
  ('major', 16, 'The Jewlery Thief', 'Obtain any 3 rings from the Dagganoth Kings.', 'Duplicates are allowed on THIS tile.'),
  ('major', 17, 'What can I say, we''re good in the sac', 'Obtain 10 Giant Egg Sacs.', null),
  ('major', 18, 'CHAAARGE!', 'Obtain 1 unique drop from General Graardor.', 'This does not include: Godsword Shards (1, 2, 3), Frozen key pieces'),
  ('major', 19, 'Scavenger hunt!!', 'Fill a Stash Unit: Next to Miss Schism (Master)', 'All items must be dropped by an npc, purchased from a base shop stock, or crafted through raw materials you obtain. Items required: Abyssal Whip, Cape of Legends, Spined Chaps'),
  ('major', 20, 'Queen Black Dragon when?', 'Cut off the King Black Dragon''s heads.', 'Obtain either the Kbd heads or the Draconic visage.'),
  ('major', 21, 'Ask Bird if you can borrow one?', 'Obtain any Crystal seed.', 'This includes the following: Enhanced, Weapon, Armor, Tool'),
  ('major', 22, 'Temple of Lost Ancients', 'Obtain any 2 Godwars Dungeon uniques.', 'This does not include: Godsword Shards (1, 2, 3), Ancient Ceremonial pieces, Nihil shards, Frozen key pieces, Ecumenical key shards'),
  ('major', 23, 'There''s always time to smell the flowers!', 'Obtain a Lily of the Sands drop from the Tombs of Amascut.', 'This includes all difficulty levels.'),
  ('major', 24, 'You can Fall on me with grace...', 'Obtain 1 Mad Angel unique.', 'This does not include: Ardeaglais teleport, Granite dust'),
  ('major', 25, 'Steal from Semour''s Wife', 'Obtain 1 unique drop from Commander Zilyana.', 'This does not include: Godsword Shards (1, 2, 3), Frozen key pieces');

insert into task (kind, tile_sequence, title, task, notes) values
  ('major', 26, 'Santa isn''t the only one with a huge sac', 'Obtain 10 Giant Egg Sacs.', null),
  ('major', 27, 'Queen of the Swamp', 'Obtain 1 Zulrah unique.', 'This does not include: Zul-andra teleport, Zulrah''s scales'),
  ('major', 28, 'The Fractured Archive: Team tryouts', 'Complete each raid 1 time.', 'If a team has multiple inexperienced players, these are allowed: Entry mode Theatre of Blood, Entry mode Tombs of Amascut'),
  ('major', 29, 'Sir Tiffy Cashien fucking wishes...', 'Fill a Stash Unit: Civitas illa Fortis (Elite)', 'You must obtain any piece of Sunfire Fanatic armour.'),
  ('major', 30, 'Back to the Mountain already?', 'Fill a Stash Unit: Salvager Overlook (Master)', 'Obtain 3 Hueycotal hides.'),
  ('major', 31, 'Momma needs a new handbag', 'Obtain the Immaculate Mole skin and the Pristine Spider silk.', null),
  ('major', 32, 'Scorching Bow is a very balanced weapon', 'Obtain 2 unique drops from K''ril Tsutsaroth.', 'This does not include: Godsword Shards (1, 2, 3), Frozen key pieces'),
  ('major', 33, 'The Ancient War rages on...', 'Obtain any 2 Godwars Dungeon uniques.', 'This does not include: Godsword Shards (1, 2, 3), Ancient Ceremonial pieces, Nihil shards, Frozen key pieces, Ecumenical key shards'),
  ('major', 34, 'I need another energy drink, brb...', 'Obtain 2 Awakener''s orb.', null),
  ('major', 35, 'Powered staved don''t charge themselves!', 'Obtain 1 Cache of runes.', null),
  ('major', 36, 'Not exactly the purples I had in mind...', 'Obtain 4 purple items from the Phantom Muspah.', 'This does not include: Ancient essence, Ancient brew'),
  ('major', 37, 'Oh boy what''s in here', 'Kill 1 Mimic', null),
  ('major', 38, 'In need of a transfusion...', 'Obtain 69 Vials of Blood from the Theatre of Blood.', 'This includes all difficulty levels.'),
  ('major', 39, 'Are you not entertained!?', 'Obtain 1 Fortis Colosseum unique.', 'This does not include: Dizana''s quiver'),
  ('major', 40, 'These still aren''t the purples I had in mind...', 'Obtain 4 purple items from the Phantom Muspah.', 'This does not include: Ancient essence, Ancient brew'),
  ('major', 41, 'The Fractured Archive: Team tryouts', 'Complete each raid 1 time.', 'If a team has multiple inexperienced players, these are allowed: Entry mode Theatre of Blood, Entry mode Tombs of Amascut'),
  ('major', 42, 'The Great Wall of Fire', 'Obtain a number of Fire capes equal to: (Team size - 3)', 'Good luck on your new personal best and Jad coming home with you!'),
  ('major', 43, 'The Great Wall of Fire', 'Obtain a number of Fire capes equal to: (Team size - 3)', 'Good luck on your new personal best and Jad coming home with you!'),
  ('major', 44, 'The Great Wall of Fire', 'Obtain a number of Fire capes equal to: (Team size - 3)', 'Good luck on your new personal best and Jad coming home with you!'),
  ('major', 45, 'The bird is the word', 'Obtain 1 unique drop from Kree''arra.', 'This does not include: Godsword Shards (1, 2, 3), Frozen key pieces'),
  ('major', 46, 'Locked and Loaded', 'Obtain 2,000 cannonballs or a unique from Corporeal Beast.', null),
  ('major', 47, 'Queen of the Swamp', 'Obtain 1 Zulrah unique.', 'This does not include: Zul-andra teleport, Zulrah''s scales'),
  ('major', 48, 'Chop chop!', 'Fill a Stash Unit: Enchanted Valley (Master)', 'You must obtain a Dragon Axe.'),
  ('major', 49, 'Wilderness Timeshare Retreat', 'Fill a Stash Unit: Soul Altar (Master)', 'All items must be dropped by an npc, purchased from a base shop stock, or crafted through raw materials you obtain. Items required: Dragon pickaxe, Helm of Neitiznot, Rune boots'),
  ('major', 50, 'The Fractured Archive: Team tryouts', 'Complete each raid 1 time.', 'If a team has multiple inexperienced players, these are allowed: Entry mode Theatre of Blood, Entry mode Tombs of Amascut');

insert into task (kind, tile_sequence, title, task, notes) values
  ('major', 51, 'Butch, why won''t you come home with me?', 'Obtain 1 unique item from Vardorvis.', 'This includes: Chromium ingot, Ring progress roll, Vestige, Virtus, Axe piece, Pet'),
  ('major', 52, 'Telef''s Frozen Prison', 'Obtain 1 unique item from Duke Sucellus.', 'This includes: Chromium ingot, Ring progress roll, Vestige, Virtus, Axe piece, Pet'),
  ('major', 53, 'Any Awakened Leviathan enjoyers?', 'Obtain 1 unique item from The Leviathan.', 'This includes: Chromium ingot, Ring progress roll, Vestige, Virtus, Axe piece, Pet'),
  ('major', 54, 'Yat honey... Do you miss me?.. Come back to me, Yat...', 'Obtain 1 unique item from The Whisperer.', 'This includes: Chromium ingot, Ring progress roll, Vestige, Virtus, Axe piece, Pet'),
  ('major', 55, 'Burn it all down!', 'Obtain 8 items from subuding the Wintertodt.', 'Duplicates allowed, the list includes: Bruma torch, Warm gloves, Pyromancer outfit, Tome of Fire, Dragon axe, Phoenix '),
  ('major', 56, 'Tooth Fairy? Is that you?', 'Obtain a Lizardman Fang drop from the Chambers of Xeric.', 'This includes all difficulty levels.'),
  ('major', 57, 'Take a page out of my book!', 'Fill a Stash Unit: Edgeville Monastary** (Elite)', 'Items required: 4 God book pages of the same god, duplicates included.'),
  ('major', 58, 'Gearing up for the mid game!', 'Obtain 4 unique items from Moons of Peril.', 'Four total Moon item drops; duplicates count.'),
  ('major', 59, 'Hey this is pretty good...', 'Obtain 1 Moons of Peril weapon drop.', 'Atlatl, Macuahuitl, or Blue moon spear.'),
  ('major', 60, 'Yama is blocking the path! What will you do?', 'Obtain 1 piece of Oathplate equipment.', 'This includes: Oathplate helm, Oathplate chest, Oathplate legs, Oathplate shards (450 total)'),
  ('major', 61, 'I miss Obelisk the Tormentor...', 'Obtain a Tormented Synpase or Burning Claw.', null),
  ('major', 62, 'Stop monkeying around!', 'Obtain 1 unique item from Demonic Gorillas.', 'This includes: Zenyte shards, Ballista limbs, Ballista spring, Light frame, Heavy frame, Monkey tail'),
  ('major', 63, 'Never trust a northern monkey.', 'Obtain 2 unique items from Demonic Gorillas.', 'This includes: Zenyte shards, Ballista limbs, Ballista spring, Light frame, Heavy frame, Monkey tail'),
  ('major', 64, 'The reason Laz didn''t play Bingo with us...', 'Obtain 3 unique items from Demonic Gorillas.', 'This includes: Zenyte shards, Ballista limbs, Ballista spring, Light frame, Heavy frame, Monkey tail'),
  ('major', 65, 'Don''t get my hair wet Tempy!!!', 'Obtain 2 Tempoross unique rolls.', 'Receiving 25 Soaked pages is a replacement roll for a unique, this counts as well.'),
  ('major', 66, 'Who''s got the Swag Socks?', 'Obtain any medium-clue boots.', 'This includes: Ranger, Wizard, Manacles, Holy sandals, or Climbing Boots (g)'),
  ('major', 67, 'It''s just like a huge chicken drumstick!', 'Obtain a Sarachnis Cudgel.', null),
  ('major', 68, 'The Fractured Archive: Team tryouts', 'Complete each raid 2 times.', 'For ToA you must be above invocation 150.'),
  ('major', 69, 'Just one more floor...', 'Obtain 1 unique from the Doom of Mokhaiotl.', 'Receiving the pet counts for this task.'),
  ('major', 70, 'The Frozen Door', 'Obtain 1 unique item from Nex.', 'This does not include: Ancient Ceremonial pieces, Nihil shards, Ecumenical key shards'),
  ('major', 71, 'The Evil Within', 'Obtain 1 unique item from Nex.', 'This does not include: Ancient Ceremonial pieces, Nihil shards, Ecumenical key shards'),
  ('major', 72, 'Bird''s favorite item sprite', 'Obtain 1 Crystal armour seed.', null),
  ('major', 73, 'King Black Dragon''s cousin Vinny', 'Obtain 3 Vorkath heads.', null),
  ('major', 74, 'Queen of the Swamp', 'Obtain 2 Zulrah uniques.', 'This does not include: Zul-andra teleport, Zulrah''s scales'),
  ('major', 75, 'Take your Pick.', 'Obtain a Dragon pickaxe or 2 Dragon axes.', 'Your choice.');

insert into task (kind, tile_sequence, title, task, notes) values
  ('major', 76, 'The Fractured Archive: Team tryouts', 'Complete each raid 2 times.', 'For ToA you must be above invocation 150.'),
  ('major', 77, 'May Elidinis guide you...', 'Receive 1 purple from the Tombs of Amascut.', null),
  ('major', 78, 'Wait... this isn''t TOA...', 'Fill a Stash Unit: Pyramid Plunder (Master)', 'All items must be dropped by an npc, purchased from a base shop stock, or crafted through raw materials you obtain. Items required: Pharoah''s sceptre, Menaphite Robe set'),
  ('major', 79, 'What do you mean this is only a spec weapon?', 'Obtain 1 unique from the Maggot King.', 'This includes: Elder venator fang, Crimson kisten, Pet'),
  ('major', 80, 'Steal from Joe''s toilet paper storage', 'Obtain 1 purple from the Chambers of Xeric.', null),
  ('major', 81, 'Gary Gilbert could never', 'Obtain an Obor''s club or Bryophyta''s essence.', null),
  ('major', 82, 'Shiny Magikarp', 'Obtain 1 Golden tench.', null),
  ('major', 83, 'Oh boy what''s in here', 'Kill 2 Mimics.', null),
  ('major', 84, 'They added the plumbus to the game!!', 'Obtain 1 Dragon hunter wand.', null),
  ('major', 85, 'The clan needs you to kidnap more Verzik pets...', 'Obtain 1 purple from the Theare of Blood.', null),
  ('major', 86, 'We''re starting our very own library!', 'Obtain 1 book that give''s Magic % damage.', 'This includes: Mage''s book, Tome of Fire, Tome of Water, Tome of Earth'),
  ('major', 87, 'The Executioner', 'Obtain 1 rare Vardorvis unique.', 'This includes: Chromium ingot, Ring progress roll, Vestige, Virtus, Axe piece, Pet'),
  ('major', 88, 'The Commander', 'Obtain 1 rare Duke Sucellus unique.', 'This includes: Chromium ingot, Ring progress roll, Vestige, Virtus, Axe piece, Pet'),
  ('major', 89, 'The Creature', 'Obtain 1 rare Whisperer unique.', 'This includes: Chromium ingot, Ring progress roll, Vestige, Virtus, Axe piece, Pet'),
  ('major', 90, 'The Assassin', 'Obtain 1 rare Leviathan unique.', 'This includes: Chromium ingot, Ring progress roll, Vestige, Virtus, Axe piece, Pet'),
  ('major', 91, 'Damn them! Damn them to hell!', 'Fill a Stash Unit: Catacomb of Kourend (Master)', 'All items must be dropped by an npc, purchased from a base shop stock, or crafted through raw materials you obtain. Items required: Tormented Synapse, Amulet of the Damned'),
  ('major', 92, 'Which God will bestow their favor?', 'Obtain 1 piece of God D'' Hide equipment.', null),
  ('major', 93, 'Lord of the Rings', 'Obtain each ring drop from the Dagganoth Kings.', 'This includes: Warrior ring, Berserker ring, Archer ring, Seers ring'),
  ('major', 94, 'I am the captain now.', 'Obtain 4 unique items from any of the Godwars Dungeon bosses.', 'This does not include: Godsword Shards (1, 2, 3), Ancient Ceremonial pieces, Nihil shards, Frozen key pieces, Ecumenical key shards'),
  ('major', 95, 'The Great Wall of Lava', 'Obtain a number of Fire or Infernal capes equal to: (Team size - 3) and atleast one Infernal cape', 'Good luck on your new personal best and a pet coming home with you! Each Infernal cape can substitute a firecape.'),
  ('major', 96, 'The Great Wall of Lava', 'Obtain a number of Fire or Infernal capes equal to: (Team size - 3) and atleast one Infernal cape', 'Good luck on your new personal best and a pet coming home with you! Each Infernal cape can substitute a firecape.'),
  ('major', 97, 'Venny Venny Venator', 'Obtain 2 Venator shards.', null),
  ('major', 98, 'The biggest chicken you''ve ever seen!', 'Obtain 1 Unique from Corporeal Beast.', 'This includes: Spirit Shield, Holy Elixer, Any Sigil, Jar, Pet'),
  ('major', 99, 'A Llama''s Prison', 'Obtain 1 Unique from Corporeal Beast.', 'This includes: Spirit Shield, Holy Elixer, Any Sigil, Jar, Pet'),
  ('major', 100, 'You''re wearing that..... to work?', 'Fill a Stash Unit: Lava Dragon Isle (Master)', 'All items must be dropped by an npc, purchased from a base shop stock, or crafted through raw materials you obtain. Items required: Dragon med helm, Toktz-ket-xil, Brine sabre, Rune platebody, Amulet of glory.');

insert into task (kind, tile_sequence, title, task, notes) values
  ('major', 101, 'Build-A-Moons', 'Obtain a full, matching, Moons of Peril set.', 'Any one full 4-piece Moon set obtained by the team.'),
  ('major', 102, 'Monster Hunter: Rise', 'Build a full Hueycoatl warrior.', 'Obtain enough Hueycoatl hide for the following: Coif, Body, Chaps, and Vambraces'),
  ('major', 103, 'This boss is old enough to drink!', 'Obtain a Dragon chainbody from the Kalphite Queen.', null),
  ('major', 104, 'I''ve got.... a pair of Aces!', 'Obtain 2 of the same crystal seeds.', 'This does not include the crystal acorn.'),
  ('major', 105, 'Kharidian Nights', 'Obtain 1 rare purple frorm Tombs of Amascut.', 'This includes any purple except the Osmumten''s Fang and Lightbearer.'),
  ('major', 106, 'Paradigm of Exodus', 'Obtain 1 rare purple from the Chambers of Xeric.', 'This includes any purple except the Dexterous and Arcane prayer scrolls.'),
  ('major', 107, 'Probita would be proud.', 'Obtain a collection log for a pet.', 'You are not allowed to submit an image for a pet that you already own.'),
  ('major', 108, 'I was being hunted by a DISGUSTING TOXIC PKER in the wilderness and I was skull tricked by them because they told me to turn off skull prevention options and click on them for the video. I, as a defenseless PVMer, obliged and consequently was risking...', 'Obtain 1 Voidwaker piece or Revenant Weapon attachment.', 'You should try the multi bosses with your team!'),
  ('major', 109, 'NIGHTMARE NIGHTMARE NIGHTMARE', 'Obtain 1 unique item from either Nightmare.', 'This does not include the Sleepy tablet.'),
  ('major', 110, 'The prison of Icec', 'Obtain 1 unique item from Nex.', 'This does not include: Ancient Ceremonial pieces, Nihil shards, Ecumenical key shards'),
  ('major', 111, 'We''re Doomed.', 'Obtain 1 unique from the Doom of Mokhaiotl.', 'This does not include the pet.'),
  ('major', 112, 'The Tale of Serafina', 'Obtain 1 rare purple from the Theatre of Blood.', 'This does not include the Avernic hilt.'),
  ('major', 113, 'And where did that bring you? Back to me.', 'Obtain 1 piece of Oathplate equipment.', 'This does not have a shard mercy rule.'),
  ('major', 114, 'Purple Rain - Prince', 'Obtain 1 purple from each raid or any Megarare.', 'The Final Tile. Thanks for playing! Receive 1 purple item from each raid, or any Megarare.');

-- Minors
insert into task (kind, tile_sequence, title, task, notes) values
  ('minor', null, 'The Forest Snapchat Group', 'Take a selfie at 5 different Forestry event types.', 'You must include at least one screenshot of each different event type you visit.'),
  ('minor', null, 'Chop chop!', 'Obtain 40,000 Woodcutting experience.', 'A valid submission contains a before and after picture of your experience in this skill. Adding text for how much exp you gained along with your picture proof is appreciated. More than one player can work on this task as long as all submissions add up to the required gained experience.'),
  ('minor', null, 'Why fletch?', 'Subdue the Wintertodt 10 times.', 'If multiple players want to do this, you must be in the same world and game together.'),
  ('minor', null, 'We didn''t start the fire...', 'Obtain 40,000 Firemaking experience.', 'A valid submission contains a before and after picture of your experience in this skill. Adding text for how much exp you gained along with your picture proof is appreciated. More than one player can work on this task as long as all submissions add up to the required gained experience.'),
  ('minor', null, 'But really, why fletch?', 'Get 4000 points in a single game of Wintertodt, and then finish the game.', 'More than one player can be in the game, but the screenshot has to come from a single person''s point value.'),
  ('minor', null, 'What''s hotter than Volcano?', 'Kill Zalcano 10 times.', 'If multiple players want to do this, you must be in the same world and game together.'),
  ('minor', null, 'I hope it doesn''t erupt....', 'Earn 5,000 Volcanic Mine points.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'ROCK AND STONE!', 'Obtain 40,000 Mining experience.', 'A valid submission contains a before and after picture of your experience in this skill. Adding text for how much exp you gained along with your picture proof is appreciated. More than one player can work on this task as long as all submissions add up to the required gained experience.'),
  ('minor', null, 'I see a storm coming....', 'Subdue Tempoross 10 times.', 'If multiple players want to do this, you must be in the same world and game together.'),
  ('minor', null, 'White Water Rafting', 'Board a RAFT from Catherby. Without stepping back on land, you need to catch 2 of each of the following fish off your boat:Raw Lobster, Raw Tuna, Raw Swordfish, Raw Mackerel, Raw Cod, Raw Bass, Raw Shark, Raw Karambwan, Raw Shrimps, Raw Anchovies, Raw Sardine, Raw Herring', 'You must take a picture at each Boat Fishing Spot. After you''ve caught all the fish, you must also take a selfie with the Wizard''s Tower in the background and each fish in your inventory. Hope you have a tacklebox!'),
  ('minor', null, 'Northern Raft Expedition', 'Board a RAFT from Port Piscarilius. Without stepping back on land, you need to catch 5 of each of the following fish off your boat: Raw Anglerfish, Raw Monkfish, Raw Tuna, Raw Swordfish', 'You must take a picture at each Boat Fishing Spot. After you''ve caught all the fish, you must also take a selfie with the Lighthouse in the background and each fish in your inventory. Hope you have a tacklebox!'),
  ('minor', null, 'This isn''t Fishing Trawler....', 'Catch 600 of the highest-level trawling fish YOU can catch.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Could I have a go with your bird?', 'Receive 50 Molch Pearls from Aerial Fishing.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Gone to eat lunch... watch my fishing pole!', 'Obtain 50,000 Fishing experience.', 'A valid submission contains a before and after picture of your experience in this skill. Adding text for how much exp you gained along with your picture proof is appreciated. More than one player can work on this task as long as all submissions add up to the required gained experience.'),
  ('minor', null, 'Leather boots? What are you doing here?', 'NO WIKI: Obtain a pair of leather boots through the Fishing skill.', 'No Wiki Disclaimer: If you do not complete this by the time the Major Task is completed, the wiki may be used. If you use the wiki, you must perform the "cry" emote in the picture.'),
  ('minor', null, 'Hmm... Kovac think it a gut feeling thing...', 'Forge 12 swords in the Giant''s Foundry.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'They''re building a speed boat!', 'Obtain 2 Normal dragon keel parts as drops.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'They''re building a yacht!', 'Obtain a Large dragon keel part as a drop.', null),
  ('minor', null, 'Tink, Tink, Tink!', 'Obtain 50,000 Smithing experience.', 'A valid submission contains a before and after picture of your experience in this skill. Adding text for how much exp you gained along with your picture proof is appreciated. More than one player can work on this task as long as all submissions add up to the required gained experience.'),
  ('minor', null, 'Let the Scar be no more!', 'Complete 6 Guardians of the Rift games.', 'If multiple players want to do this, you must be in the same world and game together.'),
  ('minor', null, 'Run, Escape, Craft', 'Obtain 25,000 Runecraft experience.', 'A valid submission contains a before and after picture of your experience in this skill. Adding text for how much exp you gained along with your picture proof is appreciated. More than one player can work on this task as long as all submissions add up to the required gained experience.'),
  ('minor', null, 'Shamanism is that you?', 'Fully decorate 12 Vale Totem sites.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'If a tree can bleed... can it feel pain?', 'Fletch 10,000 Headless arrows. If you''ve completed BMR, they must be seeking.', 'Logs and feathers may be required by any means. If doing seeker arrows, the blood must be obtained during the event.'),
  ('minor', null, 'Any Bushcraft surival video enjoyers?', 'Obtain 50,000 Fletching experience.', 'A valid submission contains a before and after picture of your experience in this skill. Adding text for how much exp you gained along with your picture proof is appreciated. More than one player can work on this task as long as all submissions add up to the required gained experience.'),
  ('minor', null, 'Jesse, we need to cook.', 'Complete as many Mastering Mixology rounds as it takes to pick 2 digweed plants.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.');

insert into task (kind, tile_sequence, title, task, notes) values
  ('minor', null, 'Sugar, spice and everything nice! ....now where did I put that vial of chemical X?', 'Obtain 50,000 Herblore experience.', 'A valid submission contains a before and after picture of your experience in this skill. Adding text for how much exp you gained along with your picture proof is appreciated. More than one player can work on this task as long as all submissions add up to the required gained experience.'),
  ('minor', null, 'Who is that guy waving to?', 'Collect 12 Marks of Grace.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Pkers and Agility? My favorite!', 'Collect 12 Wilderness Agility tickets without dying.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Holy Grave Robbing', 'Search the highest level Hallowed Sepulchre Coffin you can loot 6 times.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Prepping for a trip to the Barrows', 'Obtain a Strange lockpick from the Hallowed Sepulchre.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Spare change.... Spare change please....', 'Collect 40 Hallowed Marks from the Hallowed Sepulchre.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Run for your life!', 'Obtain 40,000 Agility experience.', 'A valid submission contains a before and after picture of your experience in this skill. Adding text for how much exp you gained along with your picture proof is appreciated. More than one player can work on this task as long as all submissions add up to the required gained experience.'),
  ('minor', null, 'Someone call PETA!!', 'Catch 200 Chinchompas of any colour.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Don''t forget to pet Guild Hunter Kiko!', 'Complete 10 Rumours for the Hunter Guild.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Herbie: Fully Loaded', 'Hunt and harvest the Herbiboar 12 times.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'The thrill of the hunt', 'Obtain 50,000 Hunter experience.', 'A valid submission contains a before and after picture of your experience in this skill. Adding text for how much exp you gained along with your picture proof is appreciated. More than one player can work on this task as long as all submissions add up to the required gained experience.'),
  ('minor', null, 'What are ye doing in me pockets?', 'Receive 10 non-beginner Clues from pickpocketing.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Who''s your Mummy?', 'In Pyramid Plunder, loot the furthest Golden Chest you can access 12 times.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Sticky fingers', 'Obtain 50,000 Thieving experience.', 'A valid submission contains a before and after picture of your experience in this skill. Adding text for how much exp you gained along with your picture proof is appreciated. More than one player can work on this task as long as all submissions add up to the required gained experience.'),
  ('minor', null, 'Catherby Catch N Cook', 'Board a RAFT with a RANGE from Catherby. Without stepping back on land, you need to catch and successfully cook one of each of the following fish on your boat: Raw Lobster, Raw Tuna, Raw Swordfish, Raw Shark, Raw Shrimps', 'Use a facility bottle to swap what is on your raft for a cooking range. Take a picture at the end with 1 of each cooked fish.'),
  ('minor', null, 'Southern Ocean Seafood Boil', 'Board a BOAT with a RANGE from anywhere. Without stepping back on land, you need to catch and successfully cook one of each of the following fish on your boat: Raw Giant Krill, Raw Haddock, Raw Yellowfin, Raw Halibut, Raw Bluefin', 'Use a facility bottle to swap what is on your raft for a cooking range. Take a picture at the end with 1 of each cooked fish.'),
  ('minor', null, 'Can somebody cook me up something for lunch?', 'Obtain 50,000 Cooking experience.', 'A valid submission contains a before and after picture of your experience in this skill. Adding text for how much exp you gained along with your picture proof is appreciated. More than one player can work on this task as long as all submissions add up to the required gained experience.'),
  ('minor', null, 'Getting Ahead', 'Reanimate one Ensouled Head with each tier of reanimation spell OUTSIDE of Arceeus.', 'There are 4 different reanimation spells you need to use. You need to get the drop for a head to reanimate it fresh in the location where you killed the monster. You can reanimate the head while it''s on the floor as long as it is fresh. Take a picture of the monster "alive" in each different location.'),
  ('minor', null, 'The Dog Bone industry is booming!', 'Freshly obtain and bury one of each of the following bones: Wyrmling bones, Babydragon bones, Wyrm bones, Strykewyrm bones, Wyvern bones, Dragon bones, Drake bones, Lava dragon bones, Frost dragon bones, Superior dragon bones', 'You must kill the monster and take a picture next to the loot pile and/or of you burying each of the bones. Whichever picture you decide is easier for you to take a picture of you doing it is acceptable.'),
  ('minor', null, 'In Saradomin''s light we pray...', 'Obtain 100,000 Prayer experience.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'I''m getting Chiseled this summer I swear!', 'Obtain 40,000 Crafting experience.', 'A valid submission contains a before and after picture of your experience in this skill. Adding text for how much exp you gained along with your picture proof is appreciated. More than one player can work on this task as long as all submissions add up to the required gained experience.'),
  ('minor', null, 'We went Easy on you...', 'Find and complete 10 Easy clues.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Falador Massacre 2.0', 'Find and complete 5 Medium clues.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'This shouldn''t be that HARD...', 'Find and complete 3 Hard clues.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Who''s your favorite high level boss?', 'Find and complete 2 Elite clues.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.');

insert into task (kind, tile_sequence, title, task, notes) values
  ('minor', null, 'Watson just placed an order for one of everything!?!', 'Find and complete 1 Master clues.', null),
  ('minor', null, 'I just need to top off my charges...', 'Obtain 5,000 Zulrah scales.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Bling Bling!', 'Obtain 1 Steel rings.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Crying Icicles', 'Obtain 240 Frozen tears.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'The Hash Slinging Slasher', 'Obtain 1 pair of Sulphur blades.', null),
  ('minor', null, 'Stab Stab Stab!', 'Obtain 1 pair of Earthbound tecpatli.', null),
  ('minor', null, 'Is it hot in here or is it just me?', 'Obtain 1 uncut emerald from Tzhaar-Ket or Tzhaar-Xil', 'You only need to obtain 1 or the other.'),
  ('minor', null, 'I know you haven''t been collecting your White Berries', 'Obtain 1 Leaf-bladed sword or 1 Lead-bladed battleaxe.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Become the Rat King', 'Obtain 3 Scurrius spines.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Wait... this doesn''t taste like milk...', 'Obtain 6 of any uniques from Brutus: Beef, Demonic Brutus slippers, Bottomless milk bucket, Mooleta, Regular Brutus slippers', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'What in the world is a Wolpertinger!', 'Obtain an Alchemist''s signet or an Antler guard.', null),
  ('minor', null, 'Time to clock in at the Quarry', 'Obtain 2 of any of the following items: Granite helm, Granite body, Granite legs, Granite gloves, Granite boots, Granite shield, Granite ring, Granite maul, Granite longsword, Granite hammer', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Pog Slayer!!!', 'Obtain any Slayer collection-log unique.', 'The list is massive, think of anything on the Slayer Collection-log or Slayer Boss specific logs. '),
  ('minor', null, 'We''re all mad here', 'Obtain 6 Ardeaglais teleport scrolls.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Dropping into a hot zone!', 'Obtain 6 Revenant teleport scrolls.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Zulrah used to drop 50 of these at one time!!! Okay Grandpa let''s get you back to bed...', 'Obtain 6 Zul-andra teleport scrolls.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'It''s so cold in here... Ouch that''s hot!', 'Obtain a Giantsoul amulet.', null),
  ('minor', null, 'After this, the Twisted Bow will be mine!', 'Obtain a Rune crossbow.', 'This can be crafted completely from scratch or obtained as a drop.'),
  ('minor', null, 'M'' Lady.', 'Obtain a Fedora.', null),
  ('minor', null, 'These are heavy!', 'Obtain a pair of Bronze boots and Iron boots as drops.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'These are even heavier!', 'Obtain a pair of Steel boots and Mithril boots as drops.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'If you wear these in a raid it''s a guarunteed purple!', 'Obtain a pair of purple gloves from Crawling hands.', null),
  ('minor', null, 'Yuck!', 'Obtain cabbage seeds from a Rock slug.', null),
  ('minor', null, 'Flip Flops or Slides?', 'Get a pair of flippers and a mudskipper hat from Mogres.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Forget the boots, think about the bones!!', 'Obtain any 2 pieces of a Skull sceptre as a drop.', null);

insert into task (kind, tile_sequence, title, task, notes) values
  ('minor', null, 'The finest of fabrics', 'Obtain a Xerician fabric as a drop from a Lizardman.', null),
  ('minor', null, '*anxious crab noises*', 'Obtain a Fresh crab claw and a Fresh crab shell as drops.', null),
  ('minor', null, 'GNOAAAAAAL', 'Score 3 goals in a game of Gnomeball.', null),
  ('minor', null, 'Heads will be rolling!', 'Score 2 skulls in a game of Skull ball.', 'Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'Hydration Nation', 'Everyone on your team online must drink at least one full (16.9oz/500ml) bottle of water, and come back with another one ready.', 'DRINK WATER YOU HEATHENS!'),
  ('minor', null, 'Hydro Homies', 'Everyone on your team online must drink at least one full (16.9oz/500ml) bottle of water, and come back with another one ready.', 'DRINK WATER YOU HEATHENS!'),
  ('minor', null, 'Teasing da Noobs', 'Drop a freshly made redberry pie in front of Thurgo.', 'The pie must be made from scratch.'),
  ('minor', null, 'Where it all began', 'Take a picture with two or more teammates in your best fashionscape with Tutorial Island in the background.', 'It''s encouraged to try to take the most stylish photo possible! You can duplicate your Runelite profile to make a "photo booth" profile where you can alter your plugins without messing up your main profile. Try whatever feels nice: 117HD, disabling tile markers, disabling any screen overlays, etc.'),
  ('minor', null, 'I can do my favorite raid without dying!', 'Take a picture with two or more teammates in your best fashionscape in front of your favorite Raid.', 'It''s encouraged to try to take the most stylish photo possible! You can duplicate your Runelite profile to make a "photo booth" profile where you can alter your plugins without messing up your main profile. Try whatever feels nice: 117HD, disabling tile markers, disabling any screen overlays, etc.'),
  ('minor', null, 'The pillory guard', 'Take a picture with two or more teammates in a prison setting in your best prison fashionscape.', 'It''s encouraged to try to take the most stylish photo possible! You can duplicate your Runelite profile to make a "photo booth" profile where you can alter your plugins without messing up your main profile. Try whatever feels nice: 117HD, disabling tile markers, disabling any screen overlays, etc.'),
  ('minor', null, 'Nothing like a hard days work', 'Take a picture with two or more teammates working on a farm in your best farming fashionscape.', 'It''s encouraged to try to take the most stylish photo possible! You can duplicate your Runelite profile to make a "photo booth" profile where you can alter your plugins without messing up your main profile. Try whatever feels nice: 117HD, disabling tile markers, disabling any screen overlays, etc.'),
  ('minor', null, 'Wait, you can get over there?', 'Take a picture with two or more teammates on the dock east of the Colosseum.', 'It''s encouraged to try to take the most stylish photo possible! You can duplicate your Runelite profile to make a "photo booth" profile where you can alter your plugins without messing up your main profile. Try whatever feels nice: 117HD, disabling tile markers, disabling any screen overlays, etc.'),
  ('minor', null, 'Don''t ask where I was last night', 'NO WIKI: Take a picture with these naturally spawning ground items: Spade, Leather gloves', 'No Wiki Disclaimer: If you do not complete this by the time the Major Task is completed, the wiki may be used. If you use the wiki, you must perform the "cry" emote in the picture.'),
  ('minor', null, 'Spy master', 'Take a picture of you sneaking up on any member of another team doing their current task(s).', null),
  ('minor', null, 'No no no no NO!!!', 'NO WIKI: Take a picture with two or more team members next to a naturally spawning toad batta without using the wiki', 'No Wiki Disclaimer: If you do not complete this by the time the Major Task is completed, the wiki may be used. If you use the wiki, you must perform the "cry" emote in the picture.'),
  ('minor', null, 'Capture the flag!', 'Take a picture of you holding the enemy team''s flag in a game of Castle Wars.', null),
  ('minor', null, 'Hey, come here often?', 'NO WIKI: Take a picture with each of the following: Hill, Moss, Ice, Fire', 'No Wiki Disclaimer: If you do not complete this by the time the Major Task is completed, the wiki may be used. If you use the wiki, you must perform the "cry" emote in the picture.'),
  ('minor', null, 'Delivery!', 'Take a picture of delivering cargo to 3 different Sailing ports.', 'You must be carrying a crate in the pictures at the destination port. Unless otherwise stated, all tasks are cumulative; More than one player can contribute as long as each player provides their proof.'),
  ('minor', null, 'BUT LITERALLY HOW?!', 'NO PLUGIN/WIKI: Take a picture at the ending safe in the Rogues Den minigame.', 'Wiki and Plugin use is not allowed for this task. Even after the Major Task is completed try to figure it out with your whole team and take pictures along the way!'),
  ('minor', null, 'I swear! I''m not H.A.M! I know plenty of fine monsters!', 'Take a picture blending in with the H.A.M members after stealing their full outfit.', 'This includes: Ham hood, Ham shirt, Ham robe, Ham gloves, Ham boots, Ham cloak, Ham logo'),
  ('minor', null, '"Our life expectancy is WHAT?"', 'While blending in as a Falador guard, obtain a medium clue from them as a drop.', 'The following items must be equipped:  Bronze med helm, Iron chain body, Steel sq shield, NO pants, Leather boots, ANY weapon'),
  ('minor', null, '"$15"', 'Take a picture with two or more team members while crab dancing with at least one equipped crab claw and crab helmet in front of the crab statue', 'Only one crab claw and one crab helmet must be visible in the picture, regardless of who is wearing them. The same person does not need to be wearing both.'),
  ('minor', null, 'Rat poison, Dwarven stout, and Purple dye all walk into a bar...', 'NO WIKI: Take a picture with these naturally spawning items: Rat poison, Dwarven stout, Purple dye', 'No Wiki Disclaimer: If you do not complete this by the time the Major Task is completed, the wiki may be used. If you use the wiki, you must perform the "cry" emote in the picture.'),
  ('minor', null, 'National Lampoon''s Varlamore Vacation', 'NO WIKI: Take a picture with these naturally spawning items: iron dart, eclipse red wine', 'No Wiki Disclaimer: If you do not complete this by the time the Major Task is completed, the wiki may be used. If you use the wiki, you must perform the "cry" emote in the picture.'),
  ('minor', null, 'Are these related?', 'NO WIKI: Take a picture with these naturally spawning items: white berries, burnt bones, steel plate body', 'No Wiki Disclaimer: If you do not complete this by the time the Major Task is completed, the wiki may be used. If you use the wiki, you must perform the "cry" emote in the picture.');
