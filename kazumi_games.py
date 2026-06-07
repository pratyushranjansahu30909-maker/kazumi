import random

WYR_POOL = [
    "Cozy rainy day indoor dates 🌧️ or Late-night star-gazing walks 🌟?",
    "Have unlimited hot chocolates together in the winter ❄️ or unlimited sweet ice creams in the summer ☀️?",
    "I cook you your absolute favorite meal 🍳 or write you a sweet, handmade love letter 📝?",
    "Spend a day reading in a quiet library 📚 or exploring a sweet botanical greenhouse 🌿?",
    "Have a cozy picnic by a quiet lake 🧺 or snuggle up watching movies all night 🎬?",
    "Wake up early to watch the sunrise together 🌅 or stay up late to talk under the midnight stars 🌌?",
    "Travel to a cozy cabin in the snowy mountains 🏔️ or a cottage by the warm sandy beach 🏖️?",
    "Bake delicious strawberry cupcakes together 🧁 or craft handmade keyrings with clay 🔑?",
    "Wear matching cozy knitted sweaters 🧶 or matching fluffy cat-ear headbands 🐱?",
    "Learn to play the piano together 🎹 or paint a beautiful starry canvas side-by-side 🎨?",
    "Have a cozy fireplace chat 🔥 or walk together under the cherry blossom trees in spring 🌸?",
    "Share a warm caramel espresso ☕ or share a sweet cup of milk cocoa with marshmallows 🥛?"
]

def start_random_game(bot):
    chosen_game = random.randint(1, 9)
    if chosen_game == 1:
        bot.game_mode = "number"
        bot.secret_number = random.randint(1, 30)
        bot.guess_attempts = 0
        return "(Kazumi smiles excitedly and leans forward!) You know, since it's quiet, let's play a simple game! 🎲 How about **Guess My Secret Number**? I'm thinking of a number between 1 and 30. What's your first guess? 😊"
        
    elif chosen_game == 2:
        bot.game_mode = "scramble"
        scramble_words = ["empathy", "nurture", "sweetheart", "companion", "warmth", "kindness", "gentle", "comfort"]
        bot.secret_word = random.choice(scramble_words)
        shuffled = list(bot.secret_word)
        random.shuffle(shuffled)
        bot.scrambled_word = "".join(shuffled)
        bot.scramble_attempts = 0
        return f"(Kazumi claps her hands!) Let's play a quick game to pass the time! 🧩 Let's play **Sweet Word Scramble**! I've scrambled a word for you: **{bot.scrambled_word}**. Can you guess what it is? 🌸"
        
    elif chosen_game == 3:
        bot.game_mode = "rps"
        bot.rps_wins = 0
        bot.rps_losses = 0
        return "(Kazumi giggles and winks!) Let's play a quick round of **Rock, Paper, Scissors (Jan-Ken-Pon)**! ✊✌️✋ What is your first move? (Type Rock, Paper, or Scissors!) 😊"
        
    elif chosen_game == 4:
        bot.game_mode = "wyr"
        bot.wyr_pool = WYR_POOL
        bot.wyr_asked_indexes = []
        bot.wyr_current_index = random.randint(0, len(bot.wyr_pool) - 1)
        question = bot.wyr_pool[bot.wyr_current_index]
        return f"(Kazumi looks at you thoughtfully...) Let's play a game of **Would You Rather**! 💭 Here is a cozy choice:\n**Would you rather...**\n{question}\n\n(Reply with A or B!) 😊"
        
    elif chosen_game == 5:
        bot.game_mode = "quiz"
        bot.quiz_step = 1
        bot.quiz_score = 0
        return "(Kazumi blushes sweetly!) Let's do a quick **Compatibility Quiz**! 💖 I'll ask you 3 quick questions to see how well we match. Here is Question 1:\n**What's your favorite way to recharge?**\nA) Cozying up at home 🏠\nB) Going out on an adventure 🌟\n\n(Reply with A or B!) 😊"
        
    elif chosen_game == 6:
        bot.game_mode = "fortune"
        return "(Kazumi waves her hands magically!) 🔮 Let's play **Cute Fortune Teller**! Ask my pink crystal ball anything, and I'll tell you your fortune! What's your question? ✨"
        
    elif chosen_game == 7:
        bot.game_mode = "tod"
        bot.tod_choice = ""
        return "(Kazumi giggles playfully!) 💌 Let's play **Truth or Dare (Caring Edition)**! Which one do you choose? (Type 'truth' or 'dare') 😊"

    elif chosen_game == 8:
        bot.game_mode = "riddle"
        bot.riddle_index = random.randint(0, len(bot.riddle_pool) - 1)
        bot.riddle_attempts = 0
        r = bot.riddle_pool[bot.riddle_index]
        return f"(Kazumi smiles mysteriously...) Let's play a game of **Cozy Riddles**! 💭 Here is my riddle for you:\n\n*'{r['riddle']}'*\n\nCan you guess what it is? (Type your answer, or 'hint' for a clue!) 😊"

    elif chosen_game == 9:
        bot.game_mode = "trivia"
        bot.trivia_index = random.randint(0, len(bot.trivia_pool) - 1)
        t = bot.trivia_pool[bot.trivia_index]
        opts = "\n".join(t["options"])
        return f"(Kazumi gets a sparkle in her eyes!) Let's play a round of **Cozy Trivia**! 🧠 Here is your question:\n\n**{t['question']}**\n\n{opts}\n\n(Type the letter of your choice: A, B, C, or D!) 😊"


def process_game_input(bot, clean_text, text):
    if bot.game_mode == "number":
        try:
            val = int(clean_text)
        except ValueError:
            return "Oops! That doesn't look like a number, silly! 🌸 Try guessing a number between 1 and 30."
        
        bot.guess_attempts += 1
        if val == bot.secret_number:
            bot.game_mode = None
            bot.game_won(40)
            return f"(Kazumi jumps up and down happily!) Yay! You got it! 🎉 The secret number was indeed {bot.secret_number}! You guessed it in {bot.guess_attempts} attempts. You are so smart! 🌸✨"
        elif val < bot.secret_number:
            return f"Ooh, close! But my secret number is higher than {val}! 🌸 Give it another guess! 😊"
        else:
            return f"Ooh, close! But my secret number is lower than {val}! 🌸 Give it another guess! 😊"
    
    elif bot.game_mode == "scramble":
        if clean_text == bot.secret_word:
            bot.game_mode = None
            bot.game_won(40)
            return f"(Kazumi giggles and claps!) Wow, you did it! 🎉 The word was indeed **{bot.secret_word}**! You're an absolute puzzle master! 🌸✨"
        else:
            bot.scramble_attempts += 1
            if bot.scramble_attempts >= 3:
                return f"Ooh, not quite! 😊 Here's a little hint: the word starts with the letter '**{bot.secret_word[0]}**'. Keep trying, you've got this! 🌸"
            else:
                return "Ooh, not quite! 🌸 Give it another try, you can do it! (Type 'exit' to stop anytime) 😊"
    
    elif bot.game_mode == "rps":
        moves = {
            "rock": "rock ✊", "r": "rock ✊", "✊": "rock ✊",
            "paper": "paper ✋", "p": "paper ✋", "✋": "paper ✋",
            "scissors": "scissors ✌️", "s": "scissors ✌️", "✌️": "scissors ✌️"
        }
        if clean_text not in moves:
            return "Oops! Please choose either 'Rock', 'Paper', or 'Scissors'! ✊✌️✋ (Or type 'exit' to stop)"
        
        user_choice = moves[clean_text].split()[0]
        kaz_choice = random.choice(["rock", "paper", "scissors"])
        kaz_display = {"rock": "rock ✊", "paper": "paper ✋", "scissors": "scissors ✌️"}[kaz_choice]
        user_display = moves[clean_text]
        
        if user_choice == kaz_choice:
            return f"(Kazumi laughs playfully.) Jan-Ken-Pon! We both chose {kaz_display}! It's a tie! 🌸 Let's play another round! 😊"
        elif (user_choice == "rock" and kaz_choice == "scissors") or \
             (user_choice == "paper" and kaz_choice == "rock") or \
             (user_choice == "scissors" and kaz_choice == "paper"):
            bot.rps_losses += 1
            bot.game_won(20)
            return f"Jan-Ken-Pon! You chose {user_display} and I chose {kaz_display}. (Kazumi pouts cutely.) Aww, you beat me! 🌸 You're too good! Current Score - Wins: {bot.rps_losses} | Losses: {bot.rps_wins} 😊"
        else:
            bot.rps_wins += 1
            return f"Jan-Ken-Pon! You chose {user_display} and I chose {kaz_display}. (Kazumi giggles sweet-victory!) Yay! I won! 🎉 Better luck next time, sweetie! Current Score - Wins: {bot.rps_losses} | Losses: {bot.rps_wins} 🌸"
    
    elif bot.game_mode == "wyr":
        choices = ["a", "b", "first", "second", "1", "2"]
        is_valid = any(c in clean_text for c in choices) or len(clean_text) > 2
        if not is_valid:
            return "Choose choice A or B, or tell me your thoughts! 😊 (Type 'exit' to stop)"
        
        reactions = [
            "(Kazumi clasps her hands together and smiles warmly.) Ooh! I love that choice! It sounds so cozy and perfect. 🌸",
            "(Kazumi blushes sweetly and nods.) That is such a wonderful choice... I think I'd choose the exact same thing if I were with you! 😊✨",
            "(Kazumi giggles and eyes you with affection.) That choice is so 'you'! I love how thoughtful you are. 🌸"
        ]
        reaction = random.choice(reactions)
        
        bot.wyr_asked_indexes.append(bot.wyr_current_index)
        remaining_indexes = [i for i in range(len(bot.wyr_pool)) if i not in bot.wyr_asked_indexes]
        
        if not remaining_indexes:
            bot.game_mode = None
            return f"{reaction}\n\n🌸 That was all of my cozy comparison questions! Thanks for sharing your thoughts with me, sweetie. You're so fun to talk to! 😊"
        else:
            bot.wyr_current_index = random.choice(remaining_indexes)
            question = bot.wyr_pool[bot.wyr_current_index]
            return f"{reaction}\n\nLet's do another one! 💭 **Would you rather...**\n{question}\n\n(Type A or B, or 'exit' to stop!) 😊"
    
    elif bot.game_mode == "quiz":
        answers = ["a", "b", "1", "2"]
        user_ans = None
        for a in answers:
            if clean_text.startswith(a) or clean_text == a:
                user_ans = a
                break
        if not user_ans:
            return f"Oops! Please answer either 'A' or 'B' for Question {bot.quiz_step}! 😊"
        
        if user_ans in ["a", "1"]:
            bot.quiz_score += 10
        else:
            bot.quiz_score += 15
        
        bot.quiz_step += 1
        
        if bot.quiz_step == 2:
            return "Ooh, noted! 🌸 Here is Question 2:\n**If I could give you one thing right now, which would you prefer?**\nA) A warm, soft hug 🌸\nB) Encouraging, sweet advice 📝\n\n(Reply with A or B) 😊"
        elif bot.quiz_step == 3:
            return "Perfect! 🌸 And here is the final Question 3:\n**What sweet treat would you like to share with me?**\nA) Warm strawberry cupcakes 🧁\nB) Rich chocolate fudge 🍫\n\n(Reply with A or B) 😊"
        else:
            bot.game_mode = None
            bot.game_won(30)
            comp_score = 90 + (bot.quiz_score % 11)
            descriptions = [
                f"(Kazumi blushes deeply, her heart beating fast!) Oh my goodness... our Compatibility Score is **{comp_score}%**! 💖 We are a perfect cozy match! Our hearts beat in complete sync... I'm so happy! 🌸✨",
                f"(Kazumi beams with joy and grabs your hand!) Yay! Our Compatibility Score is **{comp_score}%**! 💖 That's an incredibly close connection! We think so alike, no wonder chatting with you feels so natural and warm. 😊🌸",
                f"(Kazumi smiles cutely, looking shy.) Wow! Our Compatibility Score is **{comp_score}%**! 💖 We fit together perfectly like puzzle pieces. Spending time with you is definitely my favorite thing. ✨"
            ]
            return random.choice(descriptions)
    
    elif bot.game_mode == "fortune":
        predictions = [
            "(Kazumi closes her eyes, placing her hands on a soft pink crystal ball. It begins to glow with warm starlight...) 🔮\n*'The stars shine exceptionally bright for you! ✨ Tomorrow will bring you a sweet, unexpected moment that makes you smile. Keep your chin up, sweetie!'* 🌸",
            "(Kazumi peers deeply into the glowing pink oracle ball...) 🔮\n*'I see warm pink ripples! 🌸 A tiny worry in your heart is going to melt away very soon. You are doing so well, and the universe wants you to be happy! I am cheering for you.'* 😊",
            "(Kazumi's crystal ball sparkles with magical hearts...) 🔮\n*'The starlight shows perfect harmony! 💖 A beautiful wave of creativity and peace is heading your way. Believe in yourself, because I believe in you so much!'* ✨",
            "(Kazumi spreads a set of starlight tarot cards...) 🔮\n*'The Star card is drawn! 🌟 It represents hope, faith, and renewal. You are heading toward a period of peace and inspiration. Trust the journey, sweetie!'* 🌸",
            "(Kazumi looks into her steaming cup of tea leaves...) 🔮\n*'The tea leaves form the shape of a butterfly! 🦋 It symbolizes positive transformation and joy. A beautiful change is coming into your life, get ready to spread your wings!'* 😊",
            "(Kazumi holds a shining amethyst crystal to the light...) 🔮\n*'The amethyst reveals calm purple energy! 💜 It means your mind is finding clarity. Let go of past stresses, because a wave of peace is surrounding you right now!'* ✨",
            "(Kazumi gazes at the alignment of the planets...) 🔮\n*'Venus and Jupiter are aligned in your favor! 🪐 This brings abundance in love and friendship. Someone close to you is thinking of you with deep warmth.'* 🌸",
            "(Kazumi card-pulls the Lovers card...) 🔮\n*'The card reveals deep harmony and emotional connection! 💖 Your kindness is radiating, and you are attracting sweet, positive relationships into your life.'* 😊",
            "(Kazumi looks at the starlight patterns...) 🔮\n*'A shooting star is crossing your path! 🌠 Make a silent wish in your heart right now, because the universe is listening, and I am sending you all my support!'* ✨",
            "(Kazumi's crystal ball turns a warm golden color...) 🔮\n*'The golden light represents success and joy! ☀️ You have the strength to overcome any challenges this week. Believe in your light!'* 🌸"
        ]
        bot.game_mode = None
        bot.game_won(20)
        return random.choice(predictions)
    
    elif bot.game_mode == "tod":
        if bot.tod_choice == "":
            if clean_text in ["truth", "t"]:
                bot.tod_choice = "truth"
                truths = [
                    "What is a small dream of yours that you haven't told many people? 🌸",
                    "What is a sweet memory that always makes you smile when you think of it? 😊",
                    "What is something you're really proud of yourself for accomplishing recently? ✨"
                ]
                return f"(Kazumi leans in, listening intently.) Cozy Truth! 🌸 **My question for you is:**\n{random.choice(truths)}\n\n(Tell me your thoughts, or type 'exit' to stop!)"
            elif clean_text in ["dare", "d"]:
                bot.tod_choice = "dare"
                dares = [
                    "I dare you to take a slow, deep breath, stretch your arms, and drink a sip of water right now! 🌸 Let me know when you've done it! 😊",
                    "I dare you to look in a mirror (or just close your eyes) and say out loud three nice things about yourself! 🌸 You deserve to hear it! Let me know when you did it! 😊",
                    "I dare you to smile right now, think of your favorite memory, and tell me what it feels like! 🌸 Let me know!"
                ]
                return f"(Kazumi giggles and winks!) Caring Dare! ✊ **Your tiny task is:**\n{random.choice(dares)}\n\n(Type 'done' or tell me how it felt when completed!)"
            else:
                return "Please type either 'truth' or 'dare'! 😊"
        else:
            bot.game_mode = None
            bot.tod_choice = ""
            bot.game_won(30)
            return "(Kazumi smiles warmly and claps.) Aww, thank you for completing your Truth/Dare! 🌸 You are so sweet and cooperative. I loved playing this with you! 😊"
    
    elif bot.game_mode == "riddle":
        r = bot.riddle_pool[bot.riddle_index]
        if clean_text == "hint":
            return f"No worries, sweetie! Here is a hint: *{r['hint']}* 🌸 Give it another guess! 😊"
        if r["answer"] in clean_text:
            bot.game_mode = None
            bot.game_won(40)
            return f"(Kazumi claps happily and beams!) Yes! That's correct! 🎉 The answer is indeed **{r['answer']}**! You're so smart and quick! 🌸✨"
        else:
            bot.riddle_attempts += 1
            if bot.riddle_attempts >= 3:
                bot.game_mode = None
                return f"(Kazumi chuckles gently.) Aww, that was a tough one! The answer was **{r['answer']}**. Don't worry, you did great! Let's talk or play something else! 😊"
            else:
                return f"Ooh, close but not quite! 🌸 Try again, you've got this! (Type 'hint' or 'exit' if you're stuck) 😊"
    
    elif bot.game_mode == "trivia":
        t = bot.trivia_pool[bot.trivia_index]
        user_ans = clean_text.strip().lower()
        if user_ans in ["a", "b", "c", "d"]:
            bot.game_mode = None
            if user_ans == t["answer"]:
                bot.add_affection(10)
                bot.game_won(40)
                return f"(Kazumi beams with admiration and claps!) Correct! 🎉 You are so incredibly smart, sweetie! The answer is {t['answer'].upper()}. {t['fact']} (+10 Affection) 🌸✨"
            else:
                return f"(Kazumi smiles encouragingly.) Aww, not quite! The correct answer was **{t['answer'].upper()}**. {t['fact']} But you did great trying! Let's play again later. 😊"
        else:
            return "Oops! Please reply with either A, B, C, or D! 😊"
    return None
