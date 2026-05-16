"""Generate natural-looking accounts for registration."""
import json
import random
import sys

CATEGORIES = {
    "fruit": ["apple","mango","peach","berry","lemon","grape","melon","plum","kiwi","cherry","pear","fig","lime","olive","guava","papaya","lychee","date","prune","coconut","banana","orange","apricot","avocado","blueberry","cranberry","dragonfruit","elderberry","grapefruit","jackfruit","kumquat","mandarin","nectarine","passion","persimmon","pomelo","quince","raisin","starfruit","tangerine","watermelon","boysenberry","cantaloupe","clementine","currant","damson","durian","feijoa","gooseberry","honeydew"],
    "animal": ["fox","cat","owl","bee","wolf","deer","hawk","lion","bear","duck","frog","crab","swan","crow","dove","eagle","fish","goat","hare","ibis","jay","kite","lark","mole","newt","orca","puma","quail","robin","seal","toad","viper","wren","yak","zebra","ant","bat","cod","dog","eel","elk","emu","fly","gnu","hen","hog","imp","koi","lynx","moth","ox"],
    "plant": ["rose","lily","fern","moss","sage","mint","iris","palm","vine","reed","oak","elm","ivy","aloe","basil","cedar","daisy","lotus","maple","orchid","pine","tulip","willow","bamboo","clover","daffodil","eucalyptus","gardenia","heather","jasmine","lavender","magnolia","nettle","oleander","peony","rosemary","sunflower","thyme","violet","wisteria","yarrow","zinnia","aster","begonia","camellia","dahlia","freesia","ginger","holly","juniper"],
    "metal": ["iron","gold","zinc","lead","tin","ruby","jade","onyx","opal","pearl","amber","brass","steel","chrome","cobalt","copper","nickel","silver","bronze","platinum","titanium","mercury","radium","barium","cesium","helium","iodine","neon","argon","boron","carbon","lithium","sodium","sulfur","silicon","calcium","magnesium","aluminum","potassium","manganese","vanadium","gallium","germanium","arsenic","selenium","bromine","krypton","zirconium","niobium","molybdenum"],
}


def generate(count, domain, password, combo):
    parts = combo.split("+") if "+" in combo else ["fruit", "animal"]
    pool1 = CATEGORIES.get(parts[0].strip(), CATEGORIES["fruit"])
    pool2 = CATEGORIES.get(parts[1].strip() if len(parts) > 1 else "animal", CATEGORIES["animal"])

    accounts = []
    used = set()
    for i in range(count):
        for _ in range(100):
            w1 = random.choice(pool1)
            w2 = random.choice(pool2)
            n = random.randint(0, 9)
            local = f"{w1}{n}{w2}"
            if local not in used and len(local) <= 16:
                used.add(local)
                break
        accounts.append({
            "sequence": str(i + 1),
            "seed": local,
            "name": f"u_{local}",
            "provider": "wucur",
            "username": f"{local}@{domain}",
            "password": password,
        })
    return accounts


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    domain = sys.argv[2] if len(sys.argv) > 2 else "mailto.plus"
    password = sys.argv[3] if len(sys.argv) > 3 else "123Claude&Codex"
    combo = sys.argv[4] if len(sys.argv) > 4 else "fruit+animal"

    accounts = generate(count, domain, password, combo)
    print(json.dumps(accounts, ensure_ascii=False, indent=2))
