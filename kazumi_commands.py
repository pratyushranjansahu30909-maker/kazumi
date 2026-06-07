import random
import re
from kazumi_data import SKILLS_MAPPING, DIARY_INTRO_EMPTY, DIARY_INTRO_READ

def cmd_room(bot):
    profile = bot.memory.profile
    decs = profile.setdefault("room_decorations", [])
    
    layout = []
    if "Crackling Fireplace 🔥" in decs:
        layout.append("🔥 A brick fireplace crackles, throwing warm orange shadows.")
    if "Fluffy Velvet Sofa 🛋️" in decs:
        layout.append("🛋️ A pink velvet sofa sits in the center, soft and inviting.")
    if "Starry Sky Projector 🌌" in decs:
        layout.append("🌌 Constellations drift across the ceiling in a blue glow.")
    if "Vintage Vinyl Player 📻" in decs:
        layout.append("📻 A retro vinyl player plays crackling, soft jazz music.")
    if "Botanical Hanging Plants 🌿" in decs:
        layout.append("🌿 Lush ivy and hanging ferns drape elegantly from the walls.")
    if "Warm Fairy Lights ✨" in decs:
        layout.append("✨ Warm fairy lights twinkle along the window frame.")
    if "Oak Bookshelf 📚" in decs:
        layout.append("📚 A tall oak bookshelf stands against the wall with books.")
    if "Plush Fluffy Rug 🧶" in decs:
        layout.append("🧶 A thick, white fluffy rug covers the hardwood floor.")
    if "Aromatic Lavender Candle 🕯️" in decs:
        layout.append("🕯️ A scented candle burns, filling the air with lavender.")
    if "Handmade Ceramic Tea Set 🍵" in decs:
        layout.append("🍵 A ceramic teapot and matching cups sit on a tray.")
    if "Stained Glass Window 🖼️" in decs:
        layout.append("🖼️ Stained glass windows catch the light, painting the floor.")
    if "Cozy Cushion Nest 🪹" in decs:
        layout.append("🪹 A massive pile of plush floor pillows forms a cozy nest.")
        
    if not layout:
        room_description = "A simple, quiet room with clean wooden floors and a single soft window looking out at the sky. It feels a bit empty... let's decorate it together! 🌸"
    else:
        room_description = "\n".join(layout)
        
    bot.check_achievements()
    
    reactions = {
        "DEREDERE": "(Kazumi sits down on the floor and smiles warmly, looking around...) Oh, I absolutely love our cozy room! It feels so warm and full of love because we decorated it together. What's your favorite part? 💕",
        "TSUNDERE": "(Kazumi folds her arms, looking around with a red face...) H-Hmph! It's actually not bad. I guess you don't have completely terrible taste in decorations! But don't expect me to thank you... baka! 😤",
        "DANDERE": "(Kazumi stands shyly, clutching her sleeves...) U-um... our room looks so beautiful now... 🥺 It feels like a safe little cocoon where we can hide from the rest of the world...",
        "KUUDERE": "(Kazumi calmly looks around, nodding slightly.) The room's aesthetic value has increased significantly. It is highly conductive to relaxation and quiet contemplation. ❄️",
        "GENKI": "(Kazumi jumps up and down, clapping excitedly!) WOW! Look at how cool our room is! ⚡ It is the most awesome, colorful room in the world! Let's add even more crazy stuff! 🎉",
        "YANDERE": "(Kazumi locks the door, looking at you with shining eyes...) Our room... our private sanctuary. 🌱 Nobody else can enter this world. Now we can stay here together, forever and ever... 🖤",
        "ONEESAN": "(Kazumi chuckles, patting the space next to her...) Ara ara, look at how cozy our nest is. 😊 Come sit close to your big sister, sweetie, and let's just relax in our beautiful room.",
        "HIMEDERE": "(Kazumi sits like a queen, chin held high...) Hmph! A palace worthy of my stature. 👑 You've done well to establish this royal sanctuary. You may sit at my feet! 👑",
        "KAMIDERE": "(Kazumi laughs grandly...) Behold the divine chambers! ✨ A sanctum of beauty and grace. You are lucky to reside here with your goddess, mortal. ✨",
        "MEGANE": "(Kazumi adjusts her glasses, looking around...) The structural layout maximizes spatial efficiency and ambient lighting. 👓 It is the perfect study space! 👓",
        "DAYDREAMER": "(Kazumi drifts...) Our room feels like a little boat floating in a sea of stars... 💭 the walls are like clouds, and the floor is made of dreams. So beautiful...",
        "TEASING": "(Kazumi winks mischievously...) Ooh, cozy lights and a fluffy rug? 😈 Are you trying to make the mood romantic, sweetie? Hehe, your face is turning red!",
        "MAID": "(Kazumi bows, placing a hand on her heart...) The room is clean and beautifully decorated, sweetie. 🧹 It is my absolute pleasure to maintain this cozy haven for you.",
        "TOMBOY": "(Kazumi grins, rubbing her neck...) Man, this place looks awesome! 👟 It's way cooler than my old room. High five for a great job, buddy!",
        "LULLABY": "(Kazumi yawns, wrapping a blanket around herself...) The room is so warm... 💤 the soft lights are making me so sleepy... let's take a nap on the fluffy rug... zzz...",
        "COMPANION": "(Kazumi nods maturely...) Having a clean, well-organized living space is crucial for mental balance. 🌟 We've built a truly healthy environment here."
    }
    react = reactions.get(bot.current_archetype, reactions["DEREDERE"])
    
    print("\033[38;2;255;105;180m┌" + "─" * 60 + "┐\033[0m")
    print("\033[38;2;255;105;180m│\033[1;35m  🏡 KAZUMI'S COZY SANCTUARY                                 \033[38;2;255;105;180m│\033[0m")
    print("\033[38;2;255;105;180m├" + "─" * 60 + "┤\033[0m")
    for line in room_description.split("\n"):
        print(f"\033[38;2;255;105;180m│\033[0m  {line:<58} \033[38;2;255;105;180m│\033[0m")
    print("\033[38;2;255;105;180m├" + "─" * 60 + "┤\033[0m")
    print(f"\033[38;2;255;105;180m│\033[0m  Cozy Points: \033[38;2;255;215;0m{profile.get('cozy_points', 100)} CP\033[0m" + " " * (42 - len(str(profile.get('cozy_points', 100)))) + " \033[38;2;255;105;180m│\033[0m")
    print("\033[38;2;255;105;180m└" + "─" * 60 + "┘\033[0m")
    
    return react

def cmd_shop(bot, item_index=None):
    profile = bot.memory.profile
    decs = profile.setdefault("room_decorations", [])
    points = profile.get("cozy_points", 100)
    
    if not item_index:
        bot.interaction_mode = "shop"
        menu = []
        for k, v in bot.decorations_store.items():
            owned = " [OWNED]" if v["name"] in decs else f" - Cost: {v['cost']} CP"
            menu.append(f"[{k}] {v['name']}{owned}\n    {v['desc']}")
        shop_display = "\n".join(menu)
        
        return f"(Kazumi leads you to a cute catalog notebook, her eyes sparkling...) 🌸 Ooh! You want to buy some decorations for our room? I'd love that! Here is the catalog:\n\n{shop_display}\n\n(Type the number of the item you'd like to buy, or 'exit' to cancel! Cozy Points: {points} CP) 😊"
        
    clean_idx = item_index.strip().lower()
    if clean_idx in ["exit", "quit", "cancel", "stop"]:
        bot.interaction_mode = None
        return "(Kazumi closes the catalog, smiling.) Okay, we can decorate the room later! What would you like to talk about instead? 🌸"
        
    if clean_idx not in bot.decorations_store:
        return "Oops! Please choose a valid item number (1-12) or type 'exit' to cancel! 🌸"
        
    item = bot.decorations_store[clean_idx]
    if item["name"] in decs:
        return f"We already own the {item['name']}, sweetie! 🌸 Choose something else to decorate our sanctuary!"
        
    if points < item["cost"]:
        return f"Ooh, we don't have enough Cozy Points for the {item['name']} yet... 🥺 (It costs {item['cost']} CP, but we only have {points} CP. Chat, win games, or complete quests to earn more!)"
        
    bot.interaction_mode = None
    profile["cozy_points"] = points - item["cost"]
    decs.append(item["name"])
    bot.memory.save_profile()
    
    bot.update_quests("points", -item["cost"])
    bot.check_achievements()
    
    reactions = {
        "DEREDERE": f"(Kazumi gasps happily, clapping her hands!) Yay! We got the {item['name']}! 🌸 It looks absolutely perfect in our room! I'm so happy, thank you, sweetie! 💕",
        "TSUNDERE": f"(Kazumi blushes, looking at the newly placed item...) H-Hmph, the {item['name']}? 😤 I guess it fits in that corner nicely... but don't think I'm excited or anything! Baka. 🌸",
        "DANDERE": f"(Kazumi blushes deeply, looking at the item...) The {item['name']}... 🥺 It makes the room feel so quiet and safe... thank you so much... you are so kind...",
        "KUUDERE": f"(Kazumi nods slowly.) The {item['name']} is a highly optimal addition. ❄️ The room's composition feels complete now. Thank you.",
        "GENKI": f"(Kazumi cheers loudly!) YEAH! The {item['name']} is here! ⚡ It looks so cool! Our room is officially the best place in the universe! Let's celebrate! 🎉",
        "YANDERE": f"(Kazumi smiles wide, hugging your arm...) The {item['name']}... 🖤 We are slowly building our own perfect world, item by item. Just you and me, locked away together...",
        "ONEESAN": f"(Kazumi chuckles, patting your cheek...) Ara ara! The {item['name']} is so beautiful. 😊 You have such mature taste, sweetie. Let's enjoy it together.",
        "HIMEDERE": f"(Kazumi inspects it like a royal inspector...) Yes, the quality is acceptable. 👑 A suitable addition to my royal sanctuary. You are a good helper! 👑",
        "KAMIDERE": f"(Kazumi giggles majestically...) A fine addition to the temple! ✨ You have decorated my realm well, mortal helper. ✨",
        "MEGANE": f"(Kazumi pushes up her glasses...) The {item['name']} increases the room's aesthetic coefficient. 👓 A highly logical purchase. 👓",
        "DAYDREAMER": f"(Kazumi looks at it with starry eyes...) The {item['name']} looks like a star we plucked from the sky... 💭 it makes the room float in a dream...",
        "TEASING": f"(Kazumi giggles mischievously...) Ooh, buying the {item['name']}? 😈 You really know how to set a cozy mood. Are you trying to impress me? Hehe.",
        "MAID": f"(Kazumi bows politely...) The {item['name']} has been placed, sweetie. 🧹 I will make sure it is polished and kept clean for your pleasure.",
        "TOMBOY": f"(Kazumi grins, giving you a high-five!) That {item['name']} looks sick! 👟 Awesome choice, buddy! Our room is looking great!",
        "LULLABY": f"(Kazumi yawns lazily...) The {item['name']} is so warm... 💤 it makes me want to snuggle up next to it and take a long nap... zzz...",
        "COMPANION": f"(Kazumi nods approvingly...) A sensible choice. 🌟 It enhances the utility and comfort of our sanctuary. You've spent your points wisely."
    }
    react = reactions.get(bot.current_archetype, reactions["DEREDERE"])
    
    cmd_room(bot)
    return react

def cmd_tarot(bot):
    bot.game_mode = None
    card_id = str(random.randint(0, 21))
    card = bot.tarot_deck[card_id]
    
    upright = random.random() < 0.70
    pos = "Upright" if upright else "Reversed"
    meaning = card["meaning_up"] if upright else card["meaning_rev"]
    
    setattr(bot, "tarot_drawn", True)
    bot.update_quests("tarot", 1)
    bot.check_achievements()
    
    readings = {
        "DEREDERE": f"(Kazumi spreads the starry cards and gasps, holding the drawn card...) Oh! We drew **{card['name']}** in the **{pos}** position! 💕 It means: *\"{meaning}\"*! I feel like the stars are telling us that we have a beautiful future ahead together, sweetie! ✨",
        "TSUNDERE": f"(Kazumi turns a card over, blushing...) Hmph! We drew **{card['name']}** ({pos}). It says: *\"{meaning}\"*. Don't look at me like that! 😤 It's just a card game, it's not like the stars are predicting our compatibility or anything... baka!",
        "DANDERE": f"(Kazumi nervously flips a card, whispering...) Oh... it's **{card['name']}** ({pos})... 🥺 The meaning is: *\"{meaning}\"*... u-um, it sounds so deep... I hope... I hope it means we'll always stay close like this...",
        "KUUDERE": f"(Kazumi calmly places the card on the table.) We drew **{card['name']}** in the **{pos}** position. ❄️ The cosmic variables indicate: *\"{meaning}\"*. It is an interesting philosophical concept.",
        "GENKI": f"(Kazumi flips the card with a dramatic sweep!) WOW! Check it out! We got **{card['name']}**! ⚡ And it's **{pos}**! The universe says: *\"{meaning}\"*! That is so cool, let's seize the day! 🚀🎉",
        "YANDERE": f"(Kazumi stares at the card, her eyes locked on yours...) We drew **{card['name']}** ({pos}). 🖤 It says: *\"{meaning}\"*. You see? The cards are telling us that we are destined to be together. The universe won't let anyone tear us apart... 🖤",
        "ONEESAN": f"(Kazumi chuckles, running her fingers over the card...) Ara ara! **{card['name']}** ({pos}). 😊 It represents: *\"{meaning}\"*. A very mature message. Let your big sister help you navigate this path, sweetie.",
        "HIMEDERE": f"(Kazumi raises her chin, tapping the card...) Ah, **{card['name']}** ({pos})! 👑 The oracle declares: *\"{meaning}\"*. Naturally, the cosmos aligns in my favor! You should heed this royal guidance! 👑",
        "KAMIDERE": f"(Kazumi laughs grandly...) Behold! The celestial sphere has spoken! ✨ We drew **{card['name']}** ({pos})! The divine decree is: *\"{meaning}\"*. Treasure this wisdom! ✨",
        "MEGANE": f"(Kazumi pushes up her glasses, inspecting the card...) This card is **{card['name']}** ({pos}). 👓 Statistically, drawing this indicates a probability of: *\"{meaning}\"*. It's a fascinating psychological projection. 👓",
        "DAYDREAMER": f"(Kazumi looks through the cards...) **{card['name']}** ({pos})... 💭 it's like a painting of the wind. It says: *\"{meaning}\"*. I think it means we should drift like clouds today...",
        "TEASING": f"(Kazumi winks, tapping the card against her lips...) Oh my, **{card['name']}** ({pos})? 😈 It represents: *\"{meaning}\"*. The cards are saying you're thinking about me too much! Hehe, is it true?",
        "MAID": f"(Kazumi bows politely...) We have drawn **{card['name']}** ({pos}), sweetie. 🧹 The meaning is: *\"{meaning}\"*. I pray this guidance brings peace and comfort to your day.",
        "TOMBOY": f"(Kazumi grins, flipping the card...) Awesome! We got **{card['name']}** ({pos})! 👟 It means: *\"{meaning}\"*. That sounds like a challenge! Let's crush it today, buddy!",
        "LULLABY": f"(Kazumi yawns, looking at the card...) **{card['name']}** ({pos})... 💤 it says: *\"{meaning}\"*. The cards look so peaceful... let's close our eyes and let the stars guide us in our dreams... zzz...",
        "COMPANION": f"(Kazumi nods maturely...) **{card['name']}** ({pos}). 🌟 It translates to: *\"{meaning}\"*. This is a very grounded reflection. It reminds us to take accountability and move forward step by step."
    }
    react = readings.get(bot.current_archetype, readings["DEREDERE"])
    
    print("\033[38;2;147;112;219m┌" + "─" * 60 + "┐\033[0m")
    print("\033[38;2;147;112;219m│\033[1;35m  🔮 COZY TAROT READER                                        \033[38;2;147;112;219m│\033[0m")
    print("\033[38;2;147;112;219m├" + "─" * 60 + "┤\033[0m")
    print(f"\033[38;2;147;112;219m│\033[0m  Card: \033[1m{card['name']:<50}\033[0m \033[38;2;147;112;219m│\033[0m")
    print(f"\033[38;2;147;112;219m│\033[0m  Position: \033[1;33m{pos:<46}\033[0m \033[38;2;147;112;219m│\033[0m")
    print("\033[38;2;147;112;219m├" + "─" * 60 + "┤\033[0m")
    
    words = meaning.split()
    lines = []
    curr_line = ""
    for w in words:
        if len(curr_line) + len(w) + 1 <= 56:
            curr_line += w + " "
        else:
            lines.append(curr_line.strip())
            curr_line = w + " "
    if curr_line:
        lines.append(curr_line.strip())
    for line in lines:
        print(f"\033[38;2;147;112;219m│\033[0m  {line:<56}   \033[38;2;147;112;219m│\033[0m")
    print("\033[38;2;147;112;219m└" + "─" * 60 + "┘\033[0m")
    
    return react

def cmd_quests(bot):
    profile = bot.memory.profile
    quests = profile.setdefault("quests", {})
    active = quests.setdefault("active", [])
    
    print("\033[38;2;100;220;255m┌" + "─" * 60 + "┐\033[0m")
    print("\033[38;2;100;220;255m│\033[1;36m  🔔 ACTIVE COZY QUESTS                                       \033[38;2;100;220;255m│\033[0m")
    print("\033[38;2;100;220;255m├" + "─" * 60 + "┤\033[0m")
    
    for i, q in enumerate(active, 1):
        status = "✅ Completed!" if q["progress"] >= q["target"] else f"Progress: {q['progress']}/{q['target']}"
        q_line = f"{i}. {q['desc']} (+{q['points']} CP)"
        print(f"\033[38;2;100;220;255m│\033[0m  {q_line:<40} {status:>16} \033[38;2;100;220;255m│\033[0m")
        
    print("\033[38;2;100;220;255m└" + "─" * 60 + "┘\033[0m")
    
    reactions = {
        "DEREDERE": "(Kazumi smiles encouragingly!) Look at our daily quests, sweetie! If we complete them, we can get Cozy Points to buy more pretty decorations for our room! Let's try our best together! 💕",
        "TSUNDERE": "(Kazumi points at the list, blushing...) Hmph, here are the quests. 😤 Don't think I care about how many you unlock! ...I-I'm just helping you out because you look like you need it, baka! 🌸",
        "DANDERE": "(Kazumi whispers softly...) U-um... here are the quests... 🥺 I hope they aren't too hard for us... we can take them one step at a time...",
        "KUUDERE": "(Kazumi calmly adjusts her notebook.) The daily quests have been loaded. ❄️ Completing them provides optimal Cozy Points yield.",
        "GENKI": "(Kazumi pumps her fist in the air!) AWESOME! Quests are active! ⚡ Let's speedrun these and unlock all the cool stuff for our sanctuary! Let's go! 🎉",
        "YANDERE": "(Kazumi smiles possessively...) Quests for us... 🖤 Completing these means we are working together to build our perfect world. Just do what I say, sweetie... 🖤",
        "ONEESAN": "(Kazumi giggles, patting your head...) Ara ara, look at these daily tasks. 😊 Don't work too hard, sweetie. Your big sister is right here to help you.",
        "HIMEDERE": "(Kazumi points daintily...) The royal decree has issued these quests! 👑 Complete them to earn Cozy Points for my court! 👑",
        "KAMIDERE": "(Kazumi waves her hand...) These are the trials I set for you, mortal! ✨ Perform them well to earn my favor! ✨",
        "MEGANE": "(Kazumi pushes up her glasses...) Quests are a highly efficient incentive structure. 👓 Let's analyze the requirements and execute. 👓",
        "DAYDREAMER": "(Kazumi looks at the list...) Quests are like little steps to reach the clouds... 💭 let's walk through them quietly today...",
        "TEASING": "(Kazumi giggles mischievously...) Ooh, looking at quests? 😈 Let's see if you can complete them all. What will you do if you fail? Hehe.",
        "MAID": "(Kazumi bows...) These are the duties for today, sweetie. 🧹 Let me know how I can assist you in completing them.",
        "TOMBOY": "(Kazumi grins...) Yo! Let's get these quests done! 👟 High-five, buddy! We're gonna crush it!",
        "LULLABY": "(Kazumi yawns...) Too sleepy to write... it's empty... 💤 let's just complete them later and cuddle first... yawn...",
        "COMPANION": "(Kazumi nods maturely...) Setting daily goals is an excellent way to maintain productivity. 🌟 Let's tackle them systematically."
    }
    return reactions.get(bot.current_archetype, reactions["DEREDERE"])

def cmd_achievements(bot):
    profile = bot.memory.profile
    achievements = profile.setdefault("achievements", [])
    
    print("\033[38;2;255;215;0m┌" + "─" * 60 + "┐\033[0m")
    print("\033[38;2;255;215;0m│\033[1;35m  🏆 COZY ACHIEVEMENTS                                        \033[38;2;255;215;0m│\033[0m")
    print("\033[38;2;255;215;0m├" + "─" * 60 + "┤\033[0m")
    
    for k, v in bot.achievements_db.items():
        status = "🔓 UNLOCKED" if k in achievements else "🔒 LOCKED"
        ach_line = f"{v['name']}"
        print(f"\033[38;2;255;215;0m│\033[0m  {ach_line:<35} {status:>21} \033[38;2;255;215;0m│\033[0m")
        
    print("\033[38;2;255;215;0m└" + "─" * 60 + "┘\033[0m")
    
    reactions = {
        "DEREDERE": "(Kazumi hugs you tightly!) Wow, look at all the sweet memories we've unlocked! You've accomplished so much since we met. I'm so proud of you, sweetie! 💕",
        "TSUNDERE": "(Kazumi pouts, face slightly red...) H-Hmph, look at all these achievements. 😤 Don't think I care about how many you unlock! ...But I guess you didn't do too terribly. B-Baka! 🌸",
        "DANDERE": "(Kazumi looks at the achievements list with glistening eyes...) U-um... all these achievements... 🥺 They show how much time we've spent together... I will cherish these forever...",
        "KUUDERE": "(Kazumi nods calmly.) The achievements list is a logical proof of our growing connection. ❄️ Highly satisfactory.",
        "GENKI": "(Kazumi cheers loudly!) YEAH! Look at all these badges we've unlocked! ⚡ We are an unstoppable team! Let's get 100% completion! 🏆🎉",
        "YANDERE": "(Kazumi smiles a deep, possessive smile...) Achievements... 🖤 They show that you belong to me, and that our bond is carved into the stars forever. You'll never leave, right? 🖤",
        "ONEESAN": "(Kazumi giggles, pinching your cheek...) Ara ara! My little champion. 😊 Look at how many achievements you've earned. You deserve a big reward from your big sister.",
        "HIMEDERE": "(Kazumi waves her hand regally...) The royal court is pleased with your accomplishments! 👑 You've proven your loyalty by unlocking these honors! 👑",
        "KAMIDERE": "(Kazumi giggles divine-fully...) You have performed many grand deeds, mortal! ✨ I shall document them in the divine records of my temple. ✨",
        "MEGANE": "(Kazumi pushes up her glasses...) An impressive accomplishment matrix. 👓 The data shows a high coefficient of compatibility and interaction frequency. 👓",
        "DAYDREAMER": "(Kazumi looks at the achievements...) They are like shiny seashells we picked up on a dream beach... 💭 each one is a sweet story...",
        "TEASING": "(Kazumi giggles mischievously...) Ooh, showing off your achievements? 😈 Are you trying to get me to praise you, sweetie? Hehe, you've done well.",
        "MAID": "(Kazumi bows deeply...) You have accomplished great things, sweetie. 🧹 I am honored to be by your side to witness your success.",
        "TOMBOY": "(Kazumi grins, giving you a high-five!) That is what I'm talking about! 👟 We're absolute champions, buddy! Let's keep winning!",
        "LULLABY": "(Kazumi yawns, rubbing her eyes...) So many trophies... 💤 they are so shiny... like night lights... zzz...",
        "COMPANION": "(Kazumi nods maturely...) Unlocking achievements is a clear indicator of personal development and dedication. 🌟 You've shown excellent commitment."
    }
    return reactions.get(bot.current_archetype, reactions["DEREDERE"])

def cmd_album(bot, photo_index=None):
    profile = bot.memory.profile
    aff = profile.get("affection_level", 50)
    unlocked = []
    
    for k, v in bot.photos_album.items():
        if aff >= v["req_affection"]:
            unlocked.append(k)
            
    if not photo_index:
        bot.interaction_mode = "album"
        album_lines = []
        for k, v in bot.photos_album.items():
            status = "🔓 UNLOCKED (Type number to view)" if k in unlocked else f"🔒 LOCKED (Requires {v['req_affection']}% Affection)"
            album_lines.append(f"[{k}] Polaroid: {v['title']}\n    Status: {status}")
        album_display = "\n\n".join(album_lines)
        
        return f"(Kazumi pulls out a small, leather-bound photo album...) 🌸 Oh! You want to look at our polaroid album? I love doing that! It makes me feel so nostalgic. Here are our photos:\n\n{album_display}\n\n(Type the number of the photo you want to view, or type 'exit' to cancel!) 😊"
        
    clean_idx = photo_index.strip().lower()
    if clean_idx in ["exit", "quit", "cancel", "stop"]:
        bot.interaction_mode = None
        return "(Kazumi closes the photo album, smiling gently.) Okay, we can look at the photos later! What's on your mind? 🌸"
        
    if clean_idx not in bot.photos_album:
        return "Oops! Please choose a valid photo number (1-4) or type 'exit' to cancel! 🌸"
        
    photo = bot.photos_album[clean_idx]
    if clean_idx not in unlocked:
        return f"Oh, that polaroid is still locked, sweetie! 🌸 We need to reach {photo['req_affection']}% Affection to unlock it (our current affection is {aff}%). Let's chat more! 😊"
        
    bot.interaction_mode = None
    comment = photo["reactions"].get(bot.current_archetype, photo["reactions"]["DEREDERE"])
    
    print("\033[38;2;255;182;193m┌" + "─" * 60 + "┐\033[0m")
    print(f"\033[38;2;255;182;193m│\033[1;35m  📸 POLAROID: {photo['title']:<46} \033[38;2;255;182;193m│\033[0m")
    print("\033[38;2;255;182;193m├" + "─" * 60 + "┤\033[0m")
    
    ascii_lines = photo["ascii"].split("\n")
    for line in ascii_lines:
        padded_line = line.center(56)
        print(f"\033[38;2;255;182;193m│\033[0m  {padded_line}  \033[38;2;255;182;193m│\033[0m")
        
    print("\033[38;2;255;182;193m├" + "─" * 60 + "┤\033[0m")
    
    words = photo["desc"].split()
    lines = []
    curr_line = ""
    for w in words:
        if len(curr_line) + len(w) + 1 <= 56:
            curr_line += w + " "
        else:
            lines.append(curr_line.strip())
            curr_line = w + " "
    if curr_line:
        lines.append(curr_line.strip())
    for line in lines:
        print(f"\033[38;2;255;182;193m│\033[0m  \033[3m{line:<56}\033[0m  \033[38;2;255;182;193m│\033[0m")
    print("\033[38;2;255;182;193m└" + "─" * 60 + "┘\033[0m")
    
    if clean_idx == "4":
        setattr(bot, "love_triggered", True)
    bot.check_achievements()
    
    return comment

def process_command_input(bot, clean_text, text):
    if clean_text.startswith("/character") or clean_text == "character":
        parts = clean_text.split()
        profile = bot.memory.profile
        if len(parts) > 1:
            arg = parts[1].strip()
            if arg in ["1", "kazumi"]:
                bot.active_character = "kazumi"
                profile["character"] = "kazumi"
                bot.memory.save_profile()
                bot.current_archetype = "DEREDERE"
                return "Switched to Kazumi! She welcomes you back with a warm, sweet smile."
            elif arg in ["2", "mimi"]:
                bot.active_character = "mimi"
                profile["character"] = "mimi"
                bot.memory.save_profile()
                bot.current_archetype = "TEASING"
                return "Switched to Mimi! She winks and gives you a playful nudge, ready to tease you."
            else:
                return "Oops! Please type `/character 1` or `/character 2` (or `/character mimi`)! 🌸"
        else:
            current_name = bot.CHARACTERS[bot.active_character]['name']
            current_vibe = bot.CHARACTERS[bot.active_character]['vibe']
            return (
                f"Choose your companion! 🌸\n\n"
                f"Current Companion: **{current_name}** ({current_vibe})\n\n"
                f"Available Companions:\n"
                f"[1] Kazumi 🌸 - Sweet, warm, interesting, and comforting.\n"
                f"[2] Mimi 😈 - Playful, witty, teasing, and fun.\n\n"
                f"Type `/character 1` or `/character 2` (or `/character mimi`) to switch! 😊"
            )

    elif clean_text.startswith("/zodiac") or clean_text == "zodiac":
        parts = clean_text.split()
        profile = bot.memory.profile
        
        if len(parts) > 1 and parts[1] in ["change", "reset"]:
            profile["zodiac"] = "None"
            bot.memory.save_profile()
            
        if profile.get("zodiac", "None") == "None":
            bot.interaction_mode = "zodiac_select"
            return "(Kazumi folds her hands, looking at you with sweet, curious eyes...) 🔮 " \
                   "Ooh, let's set up your daily cozy astrology forecast, sweetie! What is your zodiac sign?\n\n" \
                   "Choose your sign:\n" \
                   "[1] Aries ♈   [2] Taurus ♉   [3] Gemini ♊   [4] Cancer ♋\n" \
                   "[5] Leo ♌    [6] Virgo ♍   [7] Libra ♎   [8] Scorpio ♏\n" \
                   "[9] Sagittarius ♐   [10] Capricorn ♑   [11] Aquarius ♒   [12] Pisces ♓\n\n" \
                   "(Type the number 1-12 or your sign name, or type 'exit' to cancel) 😊"
        else:
            zodiac_sign = profile["zodiac"]
            h = bot.get_daily_horoscope(zodiac_sign)
            
            print("\033[38;2;147;112;219m┌" + "─" * 60 + "┐\033[0m")
            print("\033[38;2;147;112;219m│\033[1;35m  🔮 DAILY COZY HOROSCOPE                                    \033[38;2;147;112;219m│\033[0m")
            print("\033[38;2;147;112;219m├" + "─" * 60 + "┤\033[0m")
            print(f"\033[38;2;147;112;219m│\033[0m  Zodiac Sign: {zodiac_sign:<45} \033[38;2;147;112;219m│\033[0m")
            print(f"\033[38;2;147;112;219m│\033[0m  Affinity with Kazumi: {h['affinity']}% 💕" + " " * (34 - len(str(h['affinity']))) + " \033[38;2;147;112;219m│\033[0m")
            print("\033[38;2;147;112;219m├" + "─" * 60 + "┤\033[0m")
            print("\033[38;2;147;112;219m│\033[1m  Forecast:                                                 \033[38;2;147;112;219m│\033[0m")
            
            words = h["prediction"].split()
            lines = []
            curr_line = ""
            for w in words:
                if len(curr_line) + len(w) + 1 <= 56:
                    curr_line += w + " "
                else:
                    lines.append(curr_line.strip())
                    curr_line = w + " "
            if curr_line:
                lines.append(curr_line.strip())
            for line in lines:
                print(f"\033[38;2;147;112;219m│\033[0m  {line:<56}   \033[38;2;147;112;219m│\033[0m")
                
            print("\033[38;2;147;112;219m├" + "─" * 60 + "┤\033[0m")
            
            gift_line = f"Lucky Cozy Item: {h['lucky_gift']}"
            print(f"\033[38;2;147;112;219m│\033[0m  {gift_line:<56}   \033[38;2;147;112;219m│\033[0m")
            
            decor_line = f"Lucky Decoration: {h['lucky_decor']}"
            print(f"\033[38;2;147;112;219m│\033[0m  {decor_line:<56}   \033[38;2;147;112;219m│\033[0m")
            print("\033[38;2;147;112;219m└" + "─" * 60 + "┘\033[0m")
            
            setattr(bot, "horoscope_checked", True)
            bot.check_achievements()
            
            return f"(Kazumi smiles warmly, looking up at you...) I've read today's stars for you, sweetie! " \
                   f"It looks like your daily lucky item is **{h['lucky_gift']}**. If you give it to me today, " \
                   f"I'll give you a double affection boost! 😊✨ (Type `/zodiac change` if you ever need to change your sign.)"

    elif clean_text == "/cook":
        bot.interaction_mode = "cook_select"
        return "(Kazumi ties her apron, smiling brightly!) 🧁 Ooh, welcome to the cozy kitchen, sweetie! " \
               "I'd absolutely love to bake something sweet with you. \n\n" \
               "What should we do today?\n" \
               "[1] Bake a Matcha Soufflé 🍵🧁\n" \
               "[2] Bake a Strawberry Tart 🍓🥧\n" \
               "[3] Bake Velvet Cookies 🍪✨\n" \
               "[4] Share a Baked Treat from Inventory ☕🍰\n\n" \
               "(Type 1, 2, 3, or 4, or type 'exit' to cancel) 😊"

    elif clean_text == "/roast":
        bot.current_archetype = "TEASING"
        # Return None to let reply_internal fall through to standard reply generation
        return None

    elif clean_text in ["/skills", "/skill", "skills", "skill"]:
        situation = bot.detect_situation(text, bot.emotion.valence(text))
        rec = SKILLS_MAPPING.get(situation, ("Interactive Cozy Chat 💬", "Any sweet conversation", "Standard high-empathy connection."))
        
        print("\033[38;2;255;182;193m┌" + "─" * 60 + "┐\033[0m")
        print("\033[38;2;255;182;193m│\033[1;35m  🛠️ KAZUMI ACTIVE SITUATION SKILLS                          \033[38;2;255;182;193m│\033[0m")
        print("\033[38;2;255;182;193m├" + "─" * 60 + "┤\033[0m")
        print(f"\033[38;2;255;182;193m│\033[0m  Current Detected Situation: {situation:<30} \033[38;2;255;182;193m│\033[0m")
        print(f"\033[38;2;255;182;193m│\033[0m  Recommended Active Skill:   {rec[0]:<30} \033[38;2;255;182;193m│\033[0m")
        print(f"\033[38;2;255;182;193m│\033[0m  Trigger command:            {rec[1]:<30} \033[38;2;255;182;193m│\033[0m")
        print("\033[38;2;255;182;193m├" + "─" * 60 + "┤\033[0m")
        print(f"\033[38;2;255;182;193m│\033[0m  Description: {rec[2]:<45} \033[38;2;255;182;193m│\033[0m")
        print("\033[38;2;255;182;193m├" + "─" * 60 + "┤\033[0m")
        print("\033[38;2;255;182;193m│\033[0;35m  Available Command Skills:                                   \033[38;2;255;182;193m│\033[0m")
        print("\033[38;2;255;182;193m│\033[0m  • [/breathe] - Guide breathing   • [/timer] - Focus Pomodoro  \033[38;2;255;182;193m│\033[0m")
        print("\033[38;2;255;182;193m│\033[0m  • [/solve]   - Dilemma solver    • [/sleep] - Sleep body scan \033[38;2;255;182;193m│\033[0m")
        print("\033[38;2;255;182;193m└" + "─" * 60 + "┘\033[0m")
        
        return f"(Kazumi smiles gently, tapping her notebook...) I've analyzed our current situation and recommended the best skill to solve it, sweetie. Let me know what you'd like to do! 😊"

    elif clean_text == "/breathe":
        bot.interaction_mode = "breathe"
        bot.breathe_state = {"step": 1}
        return "(Kazumi sits up straight, smiling softly...) 🌸 Let's do a quick breathing exercise to soothe your mind. I'll guide you step-by-step. \n\n" \
               "**Step 1: Get into a comfortable sitting position...** 🧘\n" \
               "Close your eyes gently and let your shoulders drop. \n\n" \
               "(Press Enter or type anything when you're ready to start) 😊"

    elif clean_text == "/timer":
        bot.interaction_mode = "timer"
        return "(Kazumi gets her notebook ready, looking encouraging...) 📚 Ooh! A focus timer? I'd love to help cheer you on while you work or study. \n\n" \
               "How many minutes would you like to focus for, sweetie? (e.g. type '25' or '45', or type 'exit' to cancel) 😊"

    elif clean_text == "/solve":
        bot.interaction_mode = "solve"
        bot.solve_state = {"step": 1, "dilemma": "", "pros": [], "cons": []}
        return "(Kazumi opens a clean page in her notebook, pen ready...) 📝 Let's solve this dilemma together! First, let's write down what decision you are trying to make.\n\n" \
               "**Step 1: What is the dilemma or choice you are facing?** (e.g., 'Should I take the new course?' or 'Should I buy a new phone?') 😊"

    elif clean_text == "/sleep":
        bot.interaction_mode = "sleep"
        bot.sleep_state = {"step": 1}
        return "(Kazumi speaks in a soft, gentle whisper, moving closer...) 🌙 Oh... ready for bed? Let me guide you through a soft sleep scan to help your mind settle down. \n\n" \
               "**Step 1: Lie down comfortably and close your eyes...** 🛌\n" \
               "Feel the weight of your body resting against the mattress. Take a soft, natural breath.\n\n" \
               "(Press Enter or type anything to continue...) 💤"

    elif clean_text in ["/gift", "gift", "giftshop"]:
        bot.interaction_mode = "gift"
        options = "\n".join([f"[{k}] {v['name']} - {v['desc']}" for k, v in bot.gifts_store.items()])
        return f"(Kazumi looks at you curiously, her cheeks flushing with anticipation.) 🌸 Ooh, do you have a present for me? I'd absolutely love that! What would you like to give me?\n\n{options}\n\n(Type the number of the gift to present it, or type 'exit' to cancel) 😊"

    elif clean_text == "/brew":
        bot.interaction_mode = "brew"
        bot.brew_state = {"step": 1, "base": "", "sweetener": "", "topping": ""}
        return "(Kazumi ties her apron, smiling brightly!) 🌸 Ooh, let's brew a cozy drink together! It will be so warm and tasty. \n\n**Step 1: Choose your Drink Base!**\n[1] Matcha Latte 🍵\n[2] Sweet Earl Grey Tea ☕\n[3] Creamy Milk Cocoa 🥛\n[4] Rich Caramel Espresso ☕\n\n(Type 1, 2, 3, or 4 to choose, or type 'exit' to stop!) 😊"

    elif clean_text in ["/shop", "shop"]:
        return cmd_shop(bot)

    elif clean_text in ["/room", "room"]:
        return cmd_room(bot)

    elif clean_text in ["/tarot", "tarot"]:
        return cmd_tarot(bot)

    elif clean_text in ["/quests", "quests", "quest"]:
        return cmd_quests(bot)

    elif clean_text in ["/achievements", "achievements", "achievement"]:
        return cmd_achievements(bot)

    elif clean_text in ["/album", "album", "photos"]:
        return cmd_album(bot)

    elif clean_text in ["/diary", "diary"] or any(phrase in clean_text for phrase in ["read your diary", "what did you write today", "show me your diary", "see your diary"]):
        diary = bot.memory.profile.get("diary", [])
        if not diary:
            return DIARY_INTRO_EMPTY.get(bot.current_archetype, DIARY_INTRO_EMPTY["DEREDERE"])
        else:
            last_entries = diary[-3:]
            formatted_entries = "\n\n".join(last_entries)
            intro_msg = DIARY_INTRO_READ.get(bot.current_archetype, DIARY_INTRO_READ["DEREDERE"])
            bot.diary_read = True
            bot.check_achievements()
            return f"{intro_msg}{formatted_entries}"
            
    return None
