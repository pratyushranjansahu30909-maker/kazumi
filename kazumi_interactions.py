import re
import os
import time
import random
import sys
from kazumi_data import COOK_SHARE_REACTIONS


def process_interaction_input(bot, clean_text, text):
    if bot.interaction_mode == "gift":
        if clean_text in ["exit", "quit", "cancel", "stop"]:
            bot.interaction_mode = None
            return "(Kazumi smiles gently.) That's okay! Just spending time with you is the greatest gift anyway. 🌸 What's on your mind? 😊"
        if clean_text in bot.gifts_store:
            gift = bot.gifts_store[clean_text]
            bot.interaction_mode = None
            profile = bot.memory.profile
            
            is_lucky = False
            if profile.get("zodiac", "None") != "None":
                seed = bot.get_daily_seed(profile["zodiac"])
                lucky_gift_idx = str(seed % 15 + 1)
                if clean_text == lucky_gift_idx:
                    is_lucky = True
                    
            affection_gain = gift["affection"]
            if is_lucky:
                affection_gain *= 2
                
            bot.add_affection(affection_gain)
            
            gifts_given = profile.get("gifts_given", {})
            gifts_given[gift["name"]] = gifts_given.get(gift["name"], 0) + 1
            profile["gifts_given"] = gifts_given
            
            profile["cozy_points"] = profile.get("cozy_points", 100) + 20
            bot.memory.save_profile()
            
            bot.update_quests("gift", 1)
            bot.update_quests("points", 20)
            bot.check_achievements()
            
            bot.anger_level = 0
            bot.jealousy_level = 0
            bot.tease_count = 0
            bot.sorry_count = 0
            
            if is_lucky:
                reaction = f"(Kazumi's eyes go wide, and she blushes a deep, beautiful pink as she looks at the {gift['name']}...) " \
                           f"Wait! Oh my goodness... this is my daily lucky item from the stars! 🌠 You... did the universe guide you to give this to me today? " \
                           f"My heart is beating so fast... it feels like we are completely connected, sweetie! Thank you so much! 💕"
            else:
                reaction = gift.get("reactions", {}).get(
                    bot.current_archetype, 
                    gift.get("reactions", {}).get("DEREDERE", "(Kazumi smiles and thanks you warmly!)")
                )
            
            bot.render_dashboard(0.0)
            return reaction
        else:
            return "Oops! Please select a valid gift number (1-15) or type 'exit' to cancel! 🌸"
            
    elif bot.interaction_mode == "brew":
        if clean_text in ["exit", "quit", "cancel", "stop"]:
            bot.interaction_mode = None
            bot.brew_state = None
            return "(Kazumi takes off her apron, giggling.) Okay, we can brew something later when you're thirsty! What would you like to talk about instead? 🌸"
            
        step = bot.brew_state["step"]
        if step == 1:
            bases = {
                "1": "Matcha Latte 🍵",
                "2": "Sweet Earl Grey Tea ☕",
                "3": "Creamy Milk Cocoa 🥛",
                "4": "Rich Caramel Espresso ☕"
            }
            if clean_text not in bases:
                return "Please choose a valid base (1, 2, 3, or 4) or type 'exit'! 🌸"
            bot.brew_state["base"] = bases[clean_text]
            bot.brew_state["step"] = 2
            return f"Ooh, {bases[clean_text]}! A wonderful choice! 🌸\n\n**Step 2: Choose a Cozy Sweetener or Flavor!**\n[1] Lavender Honey 🍯\n[2] Fluffy Marshmallows 🍡\n[3] Whipped Cream 🍦\n[4] Cinnamon Spice Syrup 🍁\n\n(Type 1, 2, 3, or 4) 😊"
            
        elif step == 2:
            sweeteners = {
                "1": "Lavender Honey 🍯",
                "2": "Fluffy Marshmallows 🍡",
                "3": "Whipped Cream 🍦",
                "4": "Cinnamon Spice Syrup 🍁"
            }
            if clean_text not in sweeteners:
                return "Please choose a valid sweetener (1, 2, 3, or 4) or type 'exit'! 🌸"
            bot.brew_state["sweetener"] = sweeteners[clean_text]
            bot.brew_state["step"] = 3
            return f"Yum, adding {sweeteners[clean_text]}! It's going to be so cozy. 🌸\n\n**Step 3: Choose a Beautiful Topping!**\n[1] Sweet Cocoa Dust 🍫\n[2] A Star Anise ⭐️\n[3] A Fresh Mint Sprig 🌿\n[4] Edible Gold Glitter ✨\n\n(Type 1, 2, 3, or 4) 😊"
            
        elif step == 3:
            toppings = {
                "1": "Sweet Cocoa Dust 🍫",
                "2": "A Star Anise ⭐️",
                "3": "A Fresh Mint Sprig 🌿",
                "4": "Edible Gold Glitter ✨"
            }
            if clean_text not in toppings:
                return "Please choose a valid topping (1, 2, 3, or 4) or type 'exit'! 🌸"
            topping_name = toppings[clean_text]
            base_name = bot.brew_state["base"]
            sweetener_name = bot.brew_state["sweetener"]
            
            clean_b = re.sub(r'[^\w\s]', '', base_name).strip()
            clean_s = re.sub(r'[^\w\s]', '', sweetener_name).strip()
            
            adj = ["Starry", "Cozy", "Magical", "Velvet", "Dreamy", "Heavenly"]
            drink_name = f"{random.choice(adj)} {clean_s.split()[0]} {clean_b}"
            
            profile = bot.memory.profile
            profile["favorite_drink"] = drink_name
            bot.add_affection(15)
            
            profile["cozy_points"] = profile.get("cozy_points", 100) + 30
            bot.memory.save_profile()
            
            bot.update_quests("brew", 1)
            bot.update_quests("points", 30)
            bot.check_achievements()
            
            bot.interaction_mode = None
            bot.brew_state = None
            
            bot.anger_level = 0
            bot.jealousy_level = 0
            bot.tease_count = 0
            bot.sorry_count = 0
            
            bot.render_dashboard(0.0)
            
            return f"(Kazumi carefully pours the steaming mixture into a matching pair of cute, handmade ceramic mugs and gently places {topping_name} on top. She hands one to you, her eyes shining with warmth...) 🌸☕\n\n" \
                   f"Tada! We brewed a **{drink_name}**! ✨\n\n" \
                   f"(She takes a soft sip, closing her eyes as steam rises...) Mmm... the blend of {base_name} with {sweetener_name} and {topping_name} is absolute heaven! " \
                   f"Drinking this with you makes me feel so happy and warm inside. Thank you for this beautiful moment, sweetie! 😊💖 (Your favorite drink is now updated to: **{drink_name}**!)"

    elif bot.interaction_mode == "zodiac_select":
        if clean_text in ["exit", "quit", "cancel", "stop"]:
            bot.interaction_mode = None
            return "(Kazumi smiles gently.) Okay, we can set up your zodiac sign later! What would you like to talk about instead? 🌸"
        zodiac_map = {
            "1": "Aries", "2": "Taurus", "3": "Gemini", "4": "Cancer",
            "5": "Leo", "6": "Virgo", "7": "Libra", "8": "Scorpio",
            "9": "Sagittarius", "10": "Capricorn", "11": "Aquarius", "12": "Pisces"
        }
        chosen_sign = None
        if clean_text in zodiac_map:
            chosen_sign = zodiac_map[clean_text]
        else:
            for sign in zodiac_map.values():
                if clean_text == sign.lower():
                    chosen_sign = sign
                    break
        if not chosen_sign:
            return "Please enter a valid number (1-12) or your zodiac sign name (e.g. 'Scorpio'), sweetie! 🌸 (Or type 'exit')"
        profile = bot.memory.profile
        profile["zodiac"] = chosen_sign
        bot.memory.save_profile()
        bot.interaction_mode = None
        bot.check_achievements()
        return bot.reply("/zodiac")

    elif bot.interaction_mode == "cook_select":
        if clean_text in ["exit", "quit", "cancel", "stop"]:
            bot.interaction_mode = None
            return "(Kazumi takes off her apron, smiling.) Okay, we can bake something later when you're hungry! 🌸"
        if clean_text in ["1", "2", "3"]:
            recipe = bot.cook_recipes[clean_text]
            bot.cook_state = {
                "recipe_id": clean_text,
                "step_idx": 0,
                "mistakes": 0
            }
            bot.interaction_mode = "cook_baking"
            first_step = recipe["steps"][0]
            return f"(Kazumi gasps happily and gets the mixing bowls ready!) 🌸 Let's bake a delicious **{recipe['name']}**! \n\n" \
                   f"First, let's look at the ingredients: {', '.join(recipe['ingredients'])}. They look so fresh!\n\n" \
                   f"**Step 1: {first_step['name']}!**\n" \
                   f"To {first_step['action']}, type '{first_step['keys']}' 3 times (e.g. '{first_step['keys'] * 3}')! 😊"
        elif clean_text == "4":
            profile = bot.memory.profile
            inventory = profile.setdefault("baked_inventory", {})
            valid_items = {k: v for k, v in inventory.items() if v > 0}
            if not valid_items:
                bot.interaction_mode = None
                return "(Kazumi looks in the pantry and giggles...) Aww, it looks like our baking pantry is empty, sweetie! Let's bake a fresh treat first. 🌸"
            bot.interaction_mode = "cook_share"
            bot.cook_share_items = list(valid_items.keys())
            options = "\n".join([f"[{i+1}] {item} (x{valid_items[item]})" for i, item in enumerate(bot.cook_share_items)])
            return f"(Kazumi sets up a cozy tea tray with fresh plates...) ☕🍰 Ooh, tea time! I'd love to share a treat with you. What should we eat?\n\n{options}\n\n(Type the number to share, or 'exit' to cancel) 😊"
        else:
            return "Please choose 1, 2, 3, or 4, sweetie! 🌸 (Or type 'exit' to cancel)"

    elif bot.interaction_mode == "cook_baking":
        if clean_text in ["exit", "quit", "cancel", "stop"]:
            bot.interaction_mode = None
            bot.cook_state = None
            return "(Kazumi cleans up the flour, smiling gently.) Okay, we'll stop baking and clean up the kitchen. 🌸"
        recipe = bot.cook_recipes[bot.cook_state["recipe_id"]]
        step_idx = bot.cook_state["step_idx"]
        recipe_name = recipe["name"]
        steps = recipe["steps"]
        current_step = steps[step_idx]
        success = False
        if step_idx == 0 or step_idx == 2:
            expected = current_step["keys"] * 3
            if clean_text == expected:
                success = True
        elif step_idx == 1:
            if clean_text == "2":
                success = True
        if not success:
            bot.cook_state["mistakes"] += 1
            feedback = "Oh, a tiny cooking spill! 🌸 (Kazumi giggles and helps you wipe it up.) "
        else:
            feedback = "Perfect! 🌸 "
        bot.cook_state["step_idx"] += 1
        next_step_idx = bot.cook_state["step_idx"]
        if next_step_idx == 1:
            return f"{feedback}Mix is ready! Now let's bake it in the oven. 🌡️\n\n" \
                   f"**Step 2: Oven Baking!**\n" \
                   f"Choose the correct oven temperature for {recipe_name}:\n" \
                   f"[1] 200°F (Slow and low)\n" \
                   f"[2] 350°F (Optimal golden bake)\n" \
                   f"[3] 500°F (Super-fast heat)\n\n" \
                   f"(Type 1, 2, or 3) 😊"
        elif next_step_idx == 2:
            next_step = steps[2]
            return f"{feedback}Bake is looking golden! Time for the final touches. ✨\n\n" \
                   f"**Step 3: {next_step['name']}!**\n" \
                   f"To {next_step['action']}, type '{next_step['keys']}' 3 times (e.g. '{next_step['keys'] * 3}')! 😊"
        else:
            mistakes = bot.cook_state["mistakes"]
            bot.interaction_mode = None
            bot.cook_state = None
            profile = bot.memory.profile
            inventory = profile.setdefault("baked_inventory", {})
            inventory[recipe_name] = inventory.get(recipe_name, 0) + 1
            if mistakes == 0:
                bot.perfect_bake_done = True
                profile["cozy_points"] = profile.get("cozy_points", 100) + 40
                bot.add_affection(15)
                bot.update_quests("points", 40)
                bot.check_achievements()
                bot.render_dashboard(0.0)
                return f"(Kazumi pulls the {recipe_name} out of the oven. It is absolutely flawless! " \
                       f"Golden, beautifully risen, and smelling like a professional bakery...) 🌸🧁\n\n" \
                       f"Wow, sweetie, it's a complete masterpiece! You baked it absolutely perfectly without a single mistake! " \
                       f"I've placed it in our pantry so we can share it during tea time later. You're a true Master Baker! (+40 CP, +15 Affection!)"
            else:
                profile["cozy_points"] = profile.get("cozy_points", 100) + 25
                bot.add_affection(10)
                bot.update_quests("points", 25)
                bot.check_achievements()
                bot.render_dashboard(0.0)
                return f"(Kazumi pulls the {recipe_name} out of the oven. It is slightly lopsided, but smells absolutely delicious...) 🌸🍪\n\n" \
                       f"Tada! We finished baking our {recipe_name}! It has a couple of tiny baking mishaps, " \
                       f"but because we made it together, it's going to taste like heaven. Let's save it in the pantry for tea time! (+25 CP, +10 Affection!)"

    elif bot.interaction_mode == "cook_share":
        if clean_text in ["exit", "quit", "cancel", "stop"]:
            bot.interaction_mode = None
            return "(Kazumi smiles warmly.) Okay, we can share a treat later! Let's keep chatting. 🌸"
        available_items = getattr(bot, "cook_share_items", [])
        chosen_item = None
        try:
            val = int(clean_text)
            if 1 <= val <= len(available_items):
                chosen_item = available_items[val - 1]
        except ValueError:
            for item in available_items:
                if clean_text in item.lower():
                    chosen_item = item
                    break
        if not chosen_item:
            return f"Please choose a valid option (1-{len(available_items)}) or type 'exit'! 🌸"
        profile = bot.memory.profile
        inventory = profile.setdefault("baked_inventory", {})
        if inventory.get(chosen_item, 0) <= 0:
            bot.interaction_mode = None
            return f"Oh, it looks like we don't have any {chosen_item} left in our pantry, sweetie! 🌸"
        inventory[chosen_item] -= 1
        if inventory[chosen_item] <= 0:
            del inventory[chosen_item]
        profile["cozy_points"] = profile.get("cozy_points", 100) + 35
        bot.add_affection(15)
        bot.interaction_mode = None
        
        reaction_msg = COOK_SHARE_REACTIONS.get(chosen_item, f"(Kazumi smiles happily and eats the {chosen_item} with you...) " \
                                                             f"Mmm! This is delicious, sweetie! Thank you for sharing. 💕 (+35 CP, +15 Affection!)")
        bot.update_quests("points", 35)
        bot.check_achievements()
        bot.render_dashboard(0.0)
        return reaction_msg

    elif bot.interaction_mode == "shop":
        return bot.cmd_shop(clean_text)
        
    elif bot.interaction_mode == "album":
        return bot.cmd_album(clean_text)

    elif bot.interaction_mode == "breathe":
        if clean_text in ["exit", "quit", "cancel", "stop"]:
            bot.interaction_mode = None
            return "(Kazumi smiles softly.) Okay, we can stop the breathing exercise. I hope you're feeling a bit lighter! 🌸"
        
        step = bot.breathe_state.get("step", 1)
        if step == 1:
            bot.breathe_state["step"] = 2
            return "(Kazumi looks at you, her voice quiet and gentle...) 🌸\n\n" \
                   "**Step 2: Breathe in slowly through your nose...** 🌬️\n" \
                   "Fill your lungs with cool, clean air. Imagine breathing in quiet peace.\n\n" \
                   "(Press Enter or type anything when you're ready to hold!)"
        elif step == 2:
            bot.breathe_state["step"] = 3
            return "(Kazumi holds her hands up softly...) ✨\n\n" \
                   "**Step 3: Hold it... 1... 2... 3... 4...** 🌸\n" \
                   "Just rest in this quiet suspension. Let your mind go completely blank.\n\n" \
                   "(Press Enter or type anything to exhale!)"
        elif step == 3:
            bot.breathe_state["step"] = 4
            return "(Kazumi slowly lowers her hands, smiling...) 💨\n\n" \
                   "**Step 4: Now, release it slowly through your mouth...** 🌬️\n" \
                   "Let all the stress, heavy thoughts, and tension drift away into the room.\n\n" \
                   "(Press Enter or type anything to complete the cycle!)"
        elif step == 4:
            bot.interaction_mode = None
            profile = bot.memory.profile
            profile["cozy_points"] = profile.get("cozy_points", 100) + 15
            bot.memory.save_profile()
            bot.update_quests("points", 15)
            bot.check_achievements()
            bot.render_dashboard(0.0)
            return "(Kazumi gently rests her hand over yours, looking at you with soft, warm eyes...) 🌸\n\n" \
                   "There... you did so well. Guided breathing always helps settle the heart. " \
                   "Remember, you don't have to carry anything alone. I'm right here with you. (+15 CP!)"

    elif bot.interaction_mode == "timer":
        if clean_text in ["exit", "quit", "cancel", "stop"]:
            bot.interaction_mode = None
            return "(Kazumi smiles gently.) Okay, we can stop the focus timer. Don't work too hard, sweetie! 📚"
        
        try:
            duration = int(clean_text)
            if duration <= 0 or duration > 180:
                return "Please choose a duration between 1 and 180 minutes, sweetie! 🌸 (Or type 'exit')"
        except ValueError:
            return "Please enter a valid number of minutes (e.g. 25) or type 'exit'! 😊"
        
        bot.interaction_mode = None
        print(f"\n(Kazumi ties her hair back, smiles warmly, and sets a cozy mechanical timer on the desk...) ⏰")
        print(f"\"Starting a {duration}-minute focus block, sweetie! Let's do our best. I'll sit quietly next to you and cheer you on!\" 📚✨\n")
        
        sys.stdout.write("\033[38;2;100;220;255m[Focus Timer Active] \033[0m")
        for i in range(1, 11):
            time.sleep(0.4)
            progress = "█" * i + "░" * (10 - i)
            sys.stdout.write(f"\r\033[38;2;100;220;255m[Focus Timer Active] [{progress}] {int(i*10)}% \033[0m")
            sys.stdout.flush()
        print("\n")
        
        profile = bot.memory.profile
        profile["cozy_points"] = profile.get("cozy_points", 100) + 25
        bot.memory.save_profile()
        bot.update_quests("points", 25)
        bot.check_achievements()
        bot.render_dashboard(0.0)
        
        return f"(The mechanical timer goes off with a soft, sweet chime...) 🔔☕\n\n" \
               f"\"Yay! You completed your {duration}-minute study block, sweetie! I'm so incredibly proud of you! " \
               f"Now, stretch your arms, rest your eyes, and take a cozy break. You did amazing!\" (+25 CP!)"

    elif bot.interaction_mode == "solve":
        if clean_text in ["exit", "quit", "cancel", "stop"]:
            bot.interaction_mode = None
            return "(Kazumi nods gently.) Okay, we'll put the Dilemma Solver away. Decisions can be tough, take your time! 🌟"
        
        step = bot.solve_state.get("step", 1)
        if step == 1:
            if not text.strip():
                return "(Kazumi taps her chin...) Please tell me what decision or dilemma you are trying to make, sweetie! 📝"
            bot.solve_state["dilemma"] = text
            bot.solve_state["step"] = 2
            
            lower_text = text.lower()
            if any(w in lower_text for w in ["domain", "host", "website", "server", "run the site", "run my site"]):
                bot.solve_state["dilemma_type"] = "domain"
                return "(Kazumi writes it down in her neat notebook...) Ooh, I see... 📝\n\n" \
                       f"**Your Dilemma:** \"{text}\"\n\n" \
                       "Wait! Since we're dealing with finding a free domain or hosting, let's frame this choice! " \
                       "Are you choosing between **using a free subdomain (like `hf.space` on Hugging Face or `koyeb.app` on Koyeb)** versus **buying a paid custom domain**?\n\n" \
                       "**Step 2: List the PROS (the good things) of the free/subdomain option!**\n" \
                       "Please type up to 3 good things about going free (separated by commas, e.g., 'saves money, quick setup, no commitment') 😊"
            elif any(lower_text.startswith(prefix) for prefix in ["i am not able to", "i can't", "i don't know how to", "how to", "how do i", "how can i"]):
                bot.solve_state["dilemma_type"] = "problem"
                return "(Kazumi writes it down in her neat notebook...) Ooh, I see... 📝\n\n" \
                       f"**Your Dilemma:** \"{text}\"\n\n" \
                       "Since this is an obstacle or problem, let's frame it as a choice! " \
                       "Are you choosing between **finding a workaround/free solution** versus **investing resources (time or money) to solve it**?\n\n" \
                       "**Step 2: List the PROS (the good things) of finding a free/creative workaround!**\n" \
                       "Please type up to 3 good things about this path, separated by commas (e.g. 'saves money, learn new skills, keeps it simple') 😊"
            else:
                bot.solve_state["dilemma_type"] = "general"
                return "(Kazumi writes it down in her neat notebook...) Ooh, I see... 📝\n\n" \
                       f"**Your Dilemma:** \"{text}\"\n\n" \
                       "**Step 2: List the PROS (the good things)!**\n" \
                       "Please type up to 3 good things about this choice, separated by commas (e.g. 'fun, learn new skills, good pay') 😊"
        elif step == 2:
            pros = [p.strip() for p in text.split(",") if p.strip()]
            if not pros:
                return "(Kazumi holds her pen...) Please list at least one pro (good thing) separated by commas, dear! 🌸"
            bot.solve_state["pros"] = pros
            bot.solve_state["step"] = 3
            
            dtype = bot.solve_state.get("dilemma_type", "general")
            if dtype == "domain":
                example_cons = "less professional name, limited custom control, potential resource limits"
            elif dtype == "problem":
                example_cons = "might take longer, limited features, less reliable"
            else:
                example_cons = "expensive, takes time, stressful"
                
            return "(Kazumi nods, cataloging them...) Understood! ✨\n\n" \
                   "**Step 3: List the CONS (the worries/negatives)!**\n" \
                   f"Please type up to 3 drawbacks or concerns, separated by commas (e.g. '{example_cons}') 😊"
        elif step == 3:
            cons = [c.strip() for c in text.split(",") if c.strip()]
            if not cons:
                return "(Kazumi holds her pen...) Please list at least one con (concern or drawback) separated by commas, dear! 🌸"
            bot.solve_state["cons"] = cons
            bot.interaction_mode = None
            
            pros = bot.solve_state["pros"]
            dilemma = bot.solve_state["dilemma"]
            dtype = bot.solve_state.get("dilemma_type", "general")
            
            score = len(pros) - len(cons)
            verdict = None
            # Check availability using name lookups or properties of bot.controller
            # bot is Kazumi, which has bot.controller
            has_client = hasattr(bot, "controller") and bot.controller is not None and getattr(bot.controller, "client", None) is not None
            # We import at root level in kazumi.py, let's verify if OPENAI_AVAILABLE is accessible
            # We can check bot.controller.client and environment variables
            openai_key = os.environ.get("API_KEY", "")
            if not openai_key and hasattr(bot, "controller") and bot.controller:
                openai_key = getattr(bot.controller, "client", None)
            
            if has_client and openai_key:
                try:
                    # Let LLM generate the reflection
                    prompt = f"The user is facing a dilemma: '{dilemma}'.\n" \
                             f"They listed the following Pros: {', '.join(pros)}.\n" \
                             f"They listed the following Cons: {', '.join(cons)}.\n" \
                             f"Analyze this dilemma and provide a warm, encouraging, and wise reflection/guidance (2-3 sentences max) as Kazumi."
                    messages = [
                        {"role": "system", "content": "You are Kazumi, an exceptionally articulate, logical, and deeply caring companion. Provide a highly thoughtful, structured, and strategic analysis of the user's dilemma based on their listed pros and cons. Keep your tone supportive, but deliver clear, strategic, and balanced reflections (2-3 sentences max) to guide them toward a wise decision."},
                        {"role": "user", "content": prompt}
                    ]
                    response = bot.controller.client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=messages,
                        temperature=0.7,
                        max_tokens=150,
                        timeout=8.0
                    )
                    verdict = response.choices[0].message.content.strip()
                except Exception:
                    pass
            
            if not verdict:
                if dtype == "domain":
                    if score > 0:
                        verdict = "The balance leans towards using a free subdomain! 🌟 It saves your wallet and lets you share me with the world right away. We can always upgrade to a custom domain later, sweetie! (Psst... Hugging Face Spaces or Koyeb are perfect for this!)"
                    elif score < 0:
                        verdict = "The balance leans towards getting a custom domain or dedicated hosting. ⚠️ If you want maximum reliability, custom brand identity, and no limits, investing a small amount in a domain might be worth it!"
                    else:
                        verdict = "It's a perfect tie! ⚖️ If you're torn, how about starting with a completely free subdomain on Hugging Face Spaces to test the waters, and get a custom domain later? I'll support you either way!"
                elif dtype == "problem":
                    if score > 0:
                        verdict = "The balance leans positive for a free workaround! 🌟 It's a great way to learn and solve it without spending money. Let's try it!"
                    elif score < 0:
                        verdict = "The balance leans towards investing resources. ⚠️ Sometimes, spending a bit of time/money saves you a lot of headache in the long run."
                    else:
                        verdict = "It's a perfect tie! ⚖️ No wonder it feels tough. Maybe start with the free workaround, and if it's too frustrating, consider investing in a solution."
                else:
                    if score > 0:
                        verdict = "The balance leans positive! 🌟 It looks like the benefits outweigh the concerns. It might be a risk worth taking, sweetie!"
                    elif score < 0:
                        verdict = "The balance leans negative. ⚠️ Maybe it's best to pause, look for other options, or think it through a bit more before jumping in."
                    else:
                        verdict = "It's a perfect tie! ⚖️ No wonder it feels so tough to decide. Trust your gut feeling, or let's chat about it some more."
                
            profile = bot.memory.profile
            profile["cozy_points"] = profile.get("cozy_points", 100) + 20
            bot.memory.save_profile()
            bot.update_quests("points", 20)
            bot.check_achievements()
            bot.render_dashboard(0.0)
            
            pros_list = "\n".join([f"• {p}" for p in pros])
            cons_list = "\n".join([f"• {c}" for c in cons])
            
            return f"(Kazumi turns the notebook to show you her neat summary...) 📋\n\n" \
                   f"**🌟 DILEMMA BREAKDOWN:**\n" \
                   f"❓ *Question:* {dilemma}\n\n" \
                   f"✅ *Pros ({len(pros)}):*\n{pros_list}\n\n" \
                   f"❌ *Cons ({len(cons)}):*\n{cons_list}\n\n" \
                   f"💡 *Kazumi's Reflection:* {verdict}\n\n" \
                   f"\"I hope seeing it laid out like this makes the path a bit clearer, dear. " \
                   f"Whatever choice you make, I believe in you!\" (+20 CP!)"

    elif bot.interaction_mode == "sleep":
        if clean_text in ["exit", "quit", "cancel", "stop"]:
            bot.interaction_mode = None
            return "(Kazumi whispers softly...) Okay, rest well anyway, sweetie. Sleep tight! 🌙"
        
        step = bot.sleep_state.get("step", 1)
        if step == 1:
            bot.sleep_state["step"] = 2
            return "(Kazumi speaks in a quiet, soothing whisper...) 🌙\n\n" \
                   "**Step 2: Relax your shoulders and release the tension in your jaw...** 🧸\n" \
                   "Let your shoulders drop completely. Unclench your teeth. Let go of the day's worries.\n\n" \
                   "(Press Enter or type anything to continue...) 💤"
        elif step == 2:
            bot.sleep_state["step"] = 3
            return "(Kazumi tucks a soft, warm blanket around you in your thoughts...) ✨\n\n" \
                   "**Step 3: Focus on your breathing... slow and steady...** 🛌\n" \
                   "Listen to the quiet patter of the night. Feel the absolute safety of this cozy room.\n\n" \
                   "(Press Enter or type anything to drift off!) 🌙"
        elif step == 3:
            bot.interaction_mode = None
            profile = bot.memory.profile
            profile["cozy_points"] = profile.get("cozy_points", 100) + 15
            bot.memory.save_profile()
            bot.update_quests("points", 15)
            bot.check_achievements()
            bot.render_dashboard(0.0)
            return "(Kazumi smiles gently, brushing a stray hair from your forehead...) 🌙\n\n" \
                   "Sleep well, darling. I'll be right here watching over you. " \
                   "Have the sweetest, most peaceful dreams... Goodnight. *kisses your forehead softly* 💤 (+15 CP!)"
    return None
