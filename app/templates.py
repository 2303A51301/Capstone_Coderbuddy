from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True)
class Template:
    name: str
    files: dict[str, str]


BASE_CSS = """
:root{color-scheme:light;--ink:#17243a;--muted:#69778d;--line:#e6eaf0;--brand:#7158e8;--mint:#69d7b6;--surface:#fff;--wash:#f6f7fb}*{box-sizing:border-box}body{margin:0;background:#f6f7fb;color:var(--ink);font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}.shell{max-width:900px;margin:6vh auto;padding:24px}.card{background:var(--surface);border:1px solid var(--line);border-radius:20px;padding:28px;box-shadow:0 20px 50px #1926440c}h1{font-size:clamp(28px,5vw,44px);line-height:1.08;letter-spacing:-1.6px;margin:8px 0 10px}.muted{color:var(--muted)}button,input{font:inherit}button{border:0;border-radius:10px;padding:11px 16px;background:var(--brand);color:white;font-weight:700;cursor:pointer}button:focus-visible,input:focus-visible{outline:3px solid #bdb1ff;outline-offset:2px}.eyebrow{font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:var(--brand);font-weight:800}.row{display:flex;gap:10px}.row input{flex:1;min-width:0;border:1px solid var(--line);border-radius:10px;padding:12px 14px}.list{list-style:none;padding:0;margin:20px 0}.list li{display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid var(--line)}.list li span{flex:1}.list li.done span{text-decoration:line-through;color:var(--muted)}.danger{background:#fff0ef;color:#b33d39;padding:8px 10px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.grid button{font-size:20px;background:#eef0f7;color:var(--ink);padding:17px}.grid button.op{background:#eeeaff;color:#573bd4}.grid button.equals{background:var(--brand);color:#fff}.display{font-size:38px;text-align:right;padding:18px;background:#f8f8fc;border-radius:12px;margin:0 0 12px;min-height:82px;overflow:auto}.hero{max-width:730px;padding:60px 0}.hero p{font-size:18px}.hero a{display:inline-block;margin-top:12px;text-decoration:none}.status{min-height:24px;color:var(--muted);font-size:14px}@media(max-width:600px){.shell{margin:0 auto;padding:16px}.card{padding:20px}.row{flex-wrap:wrap}.row button{width:100%}.hero{padding:30px 0}}
""".strip()


def _todo_template() -> Template:
    return Template("todo-app", {
        "index.html": '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#f6f7fb"><title>Daylight | Daily tasks</title><link rel="stylesheet" href="styles.css"></head><body><main class="shell"><section class="card"><p class="eyebrow">A calmer day starts here</p><h1>Your daily list</h1><p class="muted">A small, focused space for the next things that matter.</p><form id="task-form" class="row"><label class="sr-only" for="task-input">New task</label><input id="task-input" placeholder="Add a task…" autocomplete="off" required><button type="submit">Add task</button></form><p id="status" class="status" role="status" aria-live="polite"></p><ul id="task-list" class="list"></ul><p id="empty-state" class="muted">Your list is clear. Add a task to get started.</p></section></main><script src="app.js" defer></script></body></html>''',
        "styles.css": BASE_CSS + "\n.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.list button{padding:7px 10px}.check{width:20px;height:20px;accent-color:var(--brand)}",
        "app.js": '''const form=document.querySelector("#task-form"),input=document.querySelector("#task-input"),list=document.querySelector("#task-list"),empty=document.querySelector("#empty-state"),status=document.querySelector("#status");let tasks=[];function render(){list.replaceChildren();empty.hidden=tasks.length>0;for(const task of tasks){const item=document.createElement("li");item.className=task.done?"done":"";const check=document.createElement("input");check.type="checkbox";check.className="check";check.checked=task.done;check.setAttribute("aria-label",`Mark ${task.title} complete`);check.addEventListener("change",()=>{task.done=check.checked;render()});const title=document.createElement("span");title.textContent=task.title;const remove=document.createElement("button");remove.className="danger";remove.textContent="Remove";remove.setAttribute("aria-label",`Remove ${task.title}`);remove.addEventListener("click",()=>{tasks=tasks.filter(x=>x.id!==task.id);status.textContent="Task removed";render()});item.append(check,title,remove);list.append(item)}}form.addEventListener("submit",event=>{event.preventDefault();const title=input.value.trim();if(!title)return;tasks.push({id:crypto.randomUUID(),title,done:false});input.value="";status.textContent="Task added";render();input.focus()});render();''',
        "app_logic.py": '''tasks = []\n\ndef add_task(title):\n    clean = title.strip()\n    if not clean:\n        raise ValueError("Task title cannot be empty")\n    tasks.append({"title": clean, "done": False})\n    return tasks[-1]\n\ndef remove_task(title):\n    before = len(tasks)\n    tasks[:] = [task for task in tasks if task["title"] != title]\n    return len(tasks) < before\n\ndef list_tasks():\n    return list(tasks)\n''',
        "test_app.py": '''import app_logic\n\ndef setup_function():\n    app_logic.tasks.clear()\n\ndef test_add_and_list_task():\n    app_logic.add_task("Plan day")\n    assert app_logic.list_tasks() == [{"title": "Plan day", "done": False}]\n\ndef test_remove_task():\n    app_logic.add_task("Buy milk")\n    assert app_logic.remove_task("Buy milk") is True\n    assert app_logic.list_tasks() == []\n\ndef test_reject_blank_task():\n    try:\n        app_logic.add_task("  ")\n    except ValueError:\n        pass\n    else:\n        raise AssertionError("blank title should be rejected")\n''',
        "README.md": "# Daily task list\n\nOpen `index.html` in a browser. The browser UI supports adding, completing, and removing tasks. Run `python -m pytest -q` for business-logic tests.\n",
    })


def _calculator_template() -> Template:
    buttons = "".join(f'<button type="button" data-key="{k}" class="{cls}">{label}</button>' for k, label, cls in [("clear", "AC", "op"), ("/", "/", "op"), ("*", "x", "op"), ("-", "-", "op"), ("7", "7", ""), ("8", "8", ""), ("9", "9", ""), ("+", "+", "op"), ("4", "4", ""), ("5", "5", ""), ("6", "6", ""), ("equals", "=", "equals"), ("1", "1", ""), ("2", "2", ""), ("3", "3", ""), ("0", "0", ""), (".", ".", "")])
    return Template("calculator-app", {
        "index.html": f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Arc | Calculator</title><link rel="stylesheet" href="styles.css"></head><body><main class="shell"><section class="card"><p class="eyebrow">ARC / EVERYDAY TOOLS</p><h1>Calculator</h1><output id="display" class="display" aria-live="polite">0</output><div class="grid" id="keys">{buttons}</div><p id="status" class="status" role="status"></p></section></main><script src="app.js" defer></script></body></html>''',
        "styles.css": BASE_CSS + "\n.grid{grid-template-columns:repeat(4,1fr)}.grid button{min-height:62px}.grid [data-key='0']{grid-column:span 2}",
        "app.js": '''const display=document.querySelector("#display"),status=document.querySelector("#status");let current="0",stored=null,operator=null,replace=true;function show(){display.textContent=current}function key(value){if(value==="clear"){current="0";stored=null;operator=null;replace=true;status.textContent="";return show()}if(value==="equals"){if(operator===null||stored===null)return;const b=Number(current);if(operator==="/"&&b===0){current="Error";status.textContent="Cannot divide by zero";stored=null;operator=null;replace=true;return show()}const result=operator==="+"?stored+b:operator==="-"?stored-b:operator==="*"?stored*b:stored/b;current=String(Number(result.toFixed(10)));stored=null;operator=null;replace=true;return show()}if(["+","-","*","/"].includes(value)){stored=Number(current);operator=value;replace=true;return}if(value==="."){if(replace){current="0.";replace=false}else if(!current.includes("."))current+=".";return show()}if(replace||current==="0"||current==="Error"){current=value;replace=false}else current+=value;show()}document.querySelector("#keys").addEventListener("click",e=>{const b=e.target.closest("button[data-key]");if(b)key(b.dataset.key)});document.addEventListener("keydown",e=>{const k=e.key;if("0123456789.+-*/".includes(k))key(k);else if(k==="Enter"||k==="=")key("equals");else if(k==="Escape")key("clear")});''',
        "app_logic.py": '''def calculate(left, operator, right):\n    if operator == "+":\n        return left + right\n    if operator == "-":\n        return left - right\n    if operator == "*":\n        return left * right\n    if operator == "/":\n        if right == 0:\n            raise ZeroDivisionError("Cannot divide by zero")\n        return left / right\n    raise ValueError("Unsupported operator")\n''',
        "test_app.py": '''import pytest\nimport app_logic\n\ndef test_arithmetic_operations():\n    assert app_logic.calculate(2, "+", 3) == 5\n    assert app_logic.calculate(9, "-", 4) == 5\n    assert app_logic.calculate(3, "*", 4) == 12\n    assert app_logic.calculate(12, "/", 3) == 4\n\ndef test_division_by_zero():\n    with pytest.raises(ZeroDivisionError):\n        app_logic.calculate(1, "/", 0)\n\ndef test_unknown_operator():\n    with pytest.raises(ValueError):\n        app_logic.calculate(1, "%", 2)\n''',
        "README.md": "# Arc Calculator\n\nOpen `index.html` in a browser. Use the buttons or keyboard. Run `python -m pytest -q` for logic tests.\n",
    })


def _landing_template(requirement: str) -> Template:
    return Template("landing-page", {
        "index.html": '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Northstar | Studio</title><link rel="stylesheet" href="styles.css"></head><body><main class="shell"><section class="card hero"><p class="eyebrow">NORTHSTAR / INDEPENDENT STUDIO</p><h1>Make room for your next big idea.</h1><p class="muted">A thoughtful digital studio for teams ready to turn a clear vision into an unforgettable experience.</p><a href="#contact"><button type="button">Start a conversation</button></a><p class="status">Strategy · Design · Digital experiences</p></section><section id="contact" class="card"><h2>Get in touch</h2><form id="contact-form" class="row"><label class="sr-only" for="email">Your email</label><input id="email" type="email" placeholder="you@example.com" required><button>Request a callback</button></form><p id="status" role="status" class="status"></p></section></main><script src="app.js" defer></script></body></html>''',
        "styles.css": BASE_CSS + "\n.hero{padding:clamp(28px,7vw,72px);background:linear-gradient(135deg,#fff,#f0edff)}.hero h1{max-width:620px}.hero a button{background:#17243a}",
        "app.js": '''const form=document.querySelector("#contact-form"),status=document.querySelector("#status");form.addEventListener("submit",event=>{event.preventDefault();status.textContent="Thanks — your request is ready to send.";form.reset()});''',
        "app_logic.py": '''def valid_email(value):\n    clean = value.strip()\n    return "@" in clean and "." in clean.rsplit("@", 1)[-1] and " " not in clean\n''',
        "test_app.py": '''import app_logic\n\ndef test_valid_email():\n    assert app_logic.valid_email("hello@example.com") is True\n\ndef test_reject_invalid_emails():\n    assert app_logic.valid_email("not-an-email") is False\n    assert app_logic.valid_email("hello @example.com") is False\n''',
        "README.md": "# Northstar studio page\n\nOpen `index.html` in a browser. The contact form validates and shows a confirmation. Run `python -m pytest -q` to test email validation logic.\n",
    })


def _clothing_store_template(requirement: str) -> Template:
    brand = "Naveen" if re.search(r"\bnaveen\b", requirement, re.I) else "NAVEEN"
    products = [
        {"id": "tee-01", "name": "Everyday Heavyweight Tee", "category": "Tees", "price": 799, "color": "#e6ded1", "tone": "OAT", "art": "arc"},
        {"id": "tee-02", "name": "Studio Boxy T-Shirt", "category": "Tees", "price": 899, "color": "#202122", "tone": "INK", "art": "star"},
        {"id": "tee-03", "name": "Weekend Graphic Tee", "category": "Graphic tees", "price": 999, "color": "#c57863", "tone": "TERRACOTTA", "art": "sun"},
        {"id": "tee-04", "name": "Essential Crew T-Shirt", "category": "Tees", "price": 699, "color": "#a7b2a1", "tone": "SAGE", "art": "line"},
        {"id": "tee-05", "name": "Relaxed Stripe Tee", "category": "Graphic tees", "price": 949, "color": "#dfd7cc", "tone": "SAND", "art": "stripe"},
        {"id": "tee-06", "name": "After Hours Black Tee", "category": "Tees", "price": 849, "color": "#45434a", "tone": "CHARCOAL", "art": "moon"},
        {"id": "tee-07", "name": "Sunday Club T-Shirt", "category": "Graphic tees", "price": 1099, "color": "#d3b6a6", "tone": "CLAY", "art": "sun"},
        {"id": "tee-08", "name": "Classic White Crew", "category": "Tees", "price": 749, "color": "#f0eee9", "tone": "CHALK", "art": "arc"},
    ]
    brand_text = html.escape(brand)
    products_json = json.dumps(products, ensure_ascii=True)
    app_js = '''const products=__PRODUCTS__;
const formatPrice=value=>new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR",maximumFractionDigits:0}).format(value);
const grid=document.querySelector("#product-grid"),search=document.querySelector("#search"),sort=document.querySelector("#sort"),count=document.querySelector("#bag-count"),cart=document.querySelector("#cart-items"),empty=document.querySelector("#cart-empty"),subtotal=document.querySelector("#subtotal"),status=document.querySelector("#store-status");
let activeCategory="All",bag=[];
const art={arc:'<path d="M92 102c8-30 20-44 36-44s28 14 36 44" fill="none" stroke="currentColor" stroke-width="4"/><circle cx="128" cy="82" r="3" fill="currentColor"/>',star:'<path d="m128 66 6 16 17 1-13 11 4 17-14-9-14 9 4-17-13-11 17-1z" fill="currentColor"/>',sun:'<circle cx="128" cy="82" r="13" fill="none" stroke="currentColor" stroke-width="4"/><path d="M128 57v-9m0 68v-9m25-25h9m-68 0h9m43-18 7-7m-50 50 7-7m0-36-7-7m50 50-7-7" stroke="currentColor" stroke-width="3"/>',line:'<path d="M111 73h34m-34 11h34m-34 11h24" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>',stripe:'<path d="M99 77h58m-58 13h58m-50 13h42" stroke="currentColor" stroke-width="4" stroke-linecap="round"/>',moon:'<path d="M137 65a19 19 0 1 0 19 31 22 22 0 0 1-19-31" fill="currentColor"/>'};
function shirt(item){return `<svg viewBox="0 0 256 210" role="img" aria-label="${item.tone} ${item.name}" class="shirt-art" style="--shirt:${item.color}"><path class="shirt-body" d="m91 34 21-12h32l21 12 35 19-17 35-20-10v91H93V78l-20 10-17-35z"/><path class="shirt-neck" d="M112 23c2 15 9 23 16 23s14-8 16-23"/><g class="shirt-print">${art[item.art]}</g></svg>`}
function visibleProducts(){const term=search.value.trim().toLowerCase();let shown=products.filter(p=>(activeCategory==="All"||p.category===activeCategory)&&(!term||`${p.name} ${p.category} ${p.tone}`.toLowerCase().includes(term)));if(sort.value==="low")shown.sort((a,b)=>a.price-b.price);if(sort.value==="high")shown.sort((a,b)=>b.price-a.price);return shown}
function renderProducts(){const shown=visibleProducts();grid.innerHTML=shown.map(p=>`<article class="product-card"><div class="product-image" style="--shirt-bg:${p.color}">${p.id==="tee-01"?'<span class="product-badge">BESTSELLER</span>':""}${shirt(p)}<span class="color-chip">${p.tone}</span></div><div class="product-meta"><div><p class="product-category">${p.category} · NAVEEN STUDIO</p><h3>${p.name}</h3></div><strong>${formatPrice(p.price)}</strong></div><div class="product-buy"><label class="sr-only" for="size-${p.id}">Choose size for ${p.name}</label><select id="size-${p.id}" class="size-select"><option value="S">S</option><option value="M" selected>M</option><option value="L">L</option><option value="XL">XL</option></select><button class="add-button" data-add="${p.id}">Add to bag <span>+</span></button></div></article>`).join("")||'<p class="no-results">No pieces match that search. Try another style.</p>';document.querySelector("#result-count").textContent=`${shown.length} pieces`}
function renderBag(){cart.replaceChildren();const pieces=bag.reduce((total,row)=>total+row.quantity,0);count.textContent=pieces;document.querySelector("#bag-total").textContent=pieces;empty.hidden=pieces>0;bag.forEach(row=>{const p=products.find(product=>product.id===row.id);const item=document.createElement("article");item.className="bag-item";item.innerHTML=`${shirt(p)}<div class="bag-item-info"><small>${p.category} · SIZE ${row.size}</small><strong>${p.name}</strong><span>${formatPrice(p.price)}</span><div class="quantity-control"><button data-qty="-1" data-id="${p.id}" data-size="${row.size}" aria-label="Remove one ${p.name}">−</button><span>${row.quantity}</span><button data-qty="1" data-id="${p.id}" data-size="${row.size}" aria-label="Add one ${p.name}">+</button><button class="remove-item" data-remove="${p.id}" data-size="${row.size}">Remove</button></div></div>`;cart.append(item)});subtotal.textContent=formatPrice(bag.reduce((sum,row)=>sum+products.find(p=>p.id===row.id).price*row.quantity,0))}
function setBagOpen(open){document.querySelector("#bag-drawer").classList.toggle("open",open);document.querySelector("#bag-backdrop").hidden=!open;document.querySelector("#bag-drawer").setAttribute("aria-hidden",String(!open))}
document.querySelector("#category-list").addEventListener("click",event=>{const button=event.target.closest("[data-category]");if(!button)return;activeCategory=button.dataset.category;document.querySelectorAll("[data-category]").forEach(node=>node.classList.toggle("active",node===button));renderProducts()});
grid.addEventListener("click",event=>{const button=event.target.closest("[data-add]");if(!button)return;const id=button.dataset.add,size=document.querySelector(`#size-${id}`).value,row=bag.find(item=>item.id===id&&item.size===size);if(row)row.quantity++;else bag.push({id,size,quantity:1});renderBag();status.textContent="Added to your bag";button.innerHTML="Added <span>✓</span>";setTimeout(()=>{if(button.isConnected)button.innerHTML='Add to bag <span>+</span>'},900)});
cart.addEventListener("click",event=>{const qty=event.target.closest("[data-qty]"),remove=event.target.closest("[data-remove]");if(qty){const row=bag.find(item=>item.id===qty.dataset.id&&item.size===qty.dataset.size);row.quantity+=Number(qty.dataset.qty);if(row.quantity<1)bag=bag.filter(item=>item!==row)}if(remove)bag=bag.filter(item=>!(item.id===remove.dataset.remove&&item.size===remove.dataset.size));renderBag()});
search.addEventListener("input",renderProducts);sort.addEventListener("change",renderProducts);document.querySelector("#bag-open").addEventListener("click",()=>setBagOpen(true));document.querySelector("#bag-close").addEventListener("click",()=>setBagOpen(false));document.querySelector("#bag-backdrop").addEventListener("click",()=>setBagOpen(false));document.addEventListener("keydown",event=>{if(event.key==="Escape")setBagOpen(false)});
document.querySelector("#checkout").addEventListener("click",()=>{if(!bag.length){status.textContent="Add a piece to your bag first";return}document.querySelector("#checkout-note").textContent="Demo checkout only — no payment will be collected.";document.querySelector("#checkout-modal").showModal()});
document.querySelector("#checkout-form").addEventListener("submit",event=>{event.preventDefault();document.querySelector("#checkout-modal").close();setBagOpen(false);bag=[];renderBag();status.textContent="Demo order confirmed. No payment was processed.";document.querySelector("#order-status").textContent="Thank you — your demo order is confirmed."});
document.querySelector("#checkout-cancel").addEventListener("click",()=>document.querySelector("#checkout-modal").close());renderProducts();renderBag();
'''.replace("__PRODUCTS__", products_json)
    html_doc = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#f8f5f1"><meta name="description" content="Thoughtful everyday clothing from {brand_text}. Discover relaxed-fit tees and essential wardrobe pieces."><title>{brand_text} — Everyday, considered</title><link rel="icon" href="favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="styles.css"></head>
<body><header class="store-header"><a class="store-logo" href="#" aria-label="{brand_text} home">{brand_text}<span>STUDIO</span></a><nav class="store-nav" aria-label="Main navigation"><a href="#shop">Shop all</a><a href="#story">Our approach</a></nav><button id="bag-open" class="bag-button" aria-label="Open shopping bag">BAG <span id="bag-count">0</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 8h14l1 12H4L5 8Zm4 0a3 3 0 0 1 6 0" fill="none" stroke="currentColor" stroke-width="1.5"/></svg></button></header>
<main><section class="shop-hero"><div class="hero-copy"><p class="overline"><span></span> CLOTHES FOR EVERY DAY</p><h1>Good clothes.<br><em>Good days.</em></h1><p>Well-made essentials with room to be yourself. Meet your new everyday favourites.</p><a class="hero-link" href="#shop">Explore the collection <span>↘</span></a></div><div class="hero-art" aria-label="Naveen Studio everyday essentials"><div class="hero-orbit"></div><div class="hero-garment">{'''<svg viewBox="0 0 256 210" role="img" aria-label="Illustrated everyday t-shirt"><path d="m91 34 21-12h32l21 12 35 19-17 35-20-10v91H93V78l-20 10-17-35z" fill="#c67b65"/><path d="M112 23c2 15 9 23 16 23s14-8 16-23" fill="none" stroke="#f2d3c4" stroke-width="3"/><path d="M113 77h30m-30 10h30" stroke="#f2d3c4" stroke-width="3" stroke-linecap="round"/></svg>'''.replace("{", "{{").replace("}", "}}")}</div><span class="hero-art-caption">THE EVERYDAY TEE<br>NO. 001 / TERRACOTTA</span><span class="hero-sticker">MADE FOR<br>THE IN-BETWEEN</span></div></section>
<section id="story" class="brand-note"><span class="brand-note-mark">N.</span><p>Less, but better. Made to be worn on repeat, not just for a season.</p><span>DESIGNED FOR REAL LIFE · EST. 2025</span></section>
<section id="shop" class="shop-section"><div class="shop-heading"><div><p class="overline">THE FIRST EDITION</p><h2>Everyday essentials</h2><p>Easy shapes. Thoughtful details. Yours to make your own.</p></div><label class="search-wrap"><span class="sr-only">Search clothing</span><svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="m13 13 4 4" stroke="currentColor" stroke-width="1.4"/></svg><input id="search" type="search" placeholder="Find your fit…" autocomplete="off"></label></div>
<div class="collection-controls"><div id="category-list" class="category-list"><button class="category-button active" data-category="All">All pieces</button><button class="category-button" data-category="Tees">T-shirts</button><button class="category-button" data-category="Graphic tees">Graphic tees</button></div><div class="collection-meta"><span id="result-count">8 pieces</span><label>Sort <select id="sort"><option value="featured">Featured</option><option value="low">Price: low to high</option><option value="high">Price: high to low</option></select></label></div></div>
<p id="store-status" class="store-status" role="status" aria-live="polite"></p><div id="product-grid" class="product-grid"></div></section>
<section class="closing-note"><p class="overline">A LITTLE LESS, A LOT MORE WEAR</p><h2>Find the pieces<br>you live in.</h2><a href="#shop">Shop the edit ↑</a></section></main>
<footer class="store-footer"><a class="store-logo" href="#">{brand_text}<span>STUDIO</span></a><p>Everyday pieces, made with intention.</p><span>© 2025 {brand_text} Studio · Demo storefront</span></footer>
<div id="bag-backdrop" class="bag-backdrop" hidden></div><aside id="bag-drawer" class="bag-drawer" aria-label="Shopping bag" aria-hidden="true"><div class="bag-heading"><div><p class="overline">YOUR EDIT</p><h2>Your bag <span id="bag-total">(0)</span></h2></div><button id="bag-close" class="close-button" aria-label="Close shopping bag">×</button></div><p id="cart-empty" class="cart-empty">Your bag is waiting for something good.</p><div id="cart-items" class="cart-items"></div><div class="bag-summary"><p><span>Subtotal</span><strong id="subtotal">₹0</strong></p><small>Shipping and taxes calculated at checkout.</small><button id="checkout" class="checkout-button">Continue to checkout <span>→</span></button><p class="demo-payment-note">Secure checkout · Demo only, no payment processing</p></div></aside>
<dialog id="checkout-modal" class="checkout-modal"><form id="checkout-form"><button type="button" id="checkout-cancel" class="close-button modal-close" aria-label="Close checkout">×</button><p class="overline">NAVEEN STUDIO · DEMO CHECKOUT</p><h2>Your details</h2><p id="checkout-note" class="checkout-note"></p><label>Full name<input name="name" autocomplete="name" required minlength="2" placeholder="Your name"></label><label>Email address<input name="email" type="email" autocomplete="email" required placeholder="you@example.com"></label><button class="checkout-button" type="submit">Place demo order <span>→</span></button><small>No payment is collected. Connect a payment provider before accepting real orders.</small></form></dialog>
<p id="order-status" class="sr-only" role="status" aria-live="polite"></p><script src="app.js" defer></script></body></html>'''
    styles = '''
:root{color-scheme:light;--ink:#282521;--muted:#88827c;--line:#e9e4dc;--paper:#faf9f6;--rose:#af5d70;--sage:#667868;--serif:'Playfair Display',Georgia,serif;--sans:'DM Sans','Segoe UI',sans-serif}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:80px}body{margin:0;background:#fbfaf7;color:var(--ink);font:13px/1.5 var(--sans),sans-serif}a{color:inherit;text-decoration:none}button,input,select{font:inherit}button{cursor:pointer}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.store-header{height:68px;padding:0 clamp(20px,7vw,100px);display:grid;grid-template-columns:1fr 1fr 1fr;align-items:center;border-bottom:1px solid #eee9e2;background:#fbfaf7}.store-logo{font:600 19px var(--serif);letter-spacing:1.5px}.store-logo span{display:block;margin-top:-3px;font:600 7px var(--sans);letter-spacing:3.1px;color:#90877f}.store-nav{display:flex;justify-content:center;gap:34px;color:#726b65;font-size:11px}.store-nav a:hover,.hero-link:hover{color:var(--rose)}.bag-button{justify-self:end;display:flex;align-items:center;gap:9px;padding:8px 0;border:0;background:none;color:#514b46;font-size:9px;letter-spacing:1.2px}.bag-button span{display:grid;place-items:center;width:20px;height:20px;border-radius:50%;background:#302d29;color:white;font-size:9px;letter-spacing:0}.bag-button svg{width:18px;height:18px}.shop-hero{display:grid;grid-template-columns:1fr 1fr;min-height:440px;margin:0 clamp(20px,7vw,100px);background:#f3eee7}.hero-copy{align-self:center;padding:56px clamp(28px,6vw,82px)}.overline{margin:0;color:#a45a68;font-size:8px;font-weight:600;letter-spacing:1.8px}.hero-copy .overline{display:flex;align-items:center;gap:8px}.hero-copy .overline span{width:19px;height:1px;background:#a45a68}.hero-copy h1{margin:20px 0 13px;font:500 clamp(43px,6vw,72px)/1.02 var(--serif);letter-spacing:-1.6px}.hero-copy h1 em{color:#a45a68;font-weight:500}.hero-copy>p:not(.overline){max-width:330px;color:#79736d;font-size:12px;line-height:1.9}.hero-link{display:inline-flex;align-items:center;gap:14px;margin-top:20px;padding-bottom:7px;border-bottom:1px solid #b8a59c;font-size:10px}.hero-link span{font-size:15px}.hero-art{position:relative;display:grid;place-items:center;min-height:390px;overflow:hidden;background:#e6d9cd}.hero-art:before,.hero-art:after{position:absolute;content:"";width:240px;height:240px;border:1px solid #ffffff55;border-radius:50%}.hero-art:after{width:330px;height:330px}.hero-orbit{position:absolute;width:410px;height:410px;border:1px solid #ffffff38;border-radius:50%}.hero-garment{position:relative;z-index:1;display:grid;place-items:center;width:min(64%,300px);aspect-ratio:1;background:linear-gradient(145deg,#d9c6b8,#e8dcd1);border-radius:50%}.hero-garment svg{width:82%;filter:drop-shadow(0 18px 14px #4e322522)}.hero-art-caption{position:absolute;right:18px;bottom:15px;color:#76665b;font:7px/1.7 var(--sans);letter-spacing:1px}.hero-sticker{position:absolute;z-index:2;top:15%;right:12%;display:grid;place-content:center;width:67px;height:67px;border:1px solid #fff9;border-radius:50%;color:#735f55;text-align:center;font-size:7px;line-height:1.5;letter-spacing:.8px;transform:rotate(9deg)}.brand-note{display:flex;align-items:center;gap:16px;margin:0 clamp(20px,7vw,100px);padding:16px 0;border-bottom:1px solid var(--line)}.brand-note-mark{display:grid;place-items:center;width:27px;height:27px;border:1px solid #c9b9ac;border-radius:50%;font:italic 14px var(--serif);color:#9e5d68}.brand-note p{flex:1;margin:0;color:#706962;font:italic 13px var(--serif)}.brand-note>span:last-child{color:#a0978d;font-size:7px;letter-spacing:1px}.shop-section{padding:68px clamp(20px,7vw,100px) 74px}.shop-heading{display:flex;align-items:end;justify-content:space-between;gap:20px}.shop-heading h2{margin:7px 0 5px;font:500 32px var(--serif);letter-spacing:-.4px}.shop-heading>div>p:last-child{margin:0;color:#89827b;font-size:10px}.search-wrap{display:flex;align-items:center;gap:8px;width:210px;padding:8px 10px;border-bottom:1px solid #cfc7be}.search-wrap svg{width:15px;height:15px;color:#847c74}.search-wrap input{width:100%;border:0;outline:0;background:transparent;color:var(--ink);font-size:10px}.search-wrap input::placeholder{color:#a59d95}.collection-controls{display:flex;align-items:center;justify-content:space-between;gap:15px;margin-top:29px;padding-bottom:12px;border-bottom:1px solid var(--line)}.category-list{display:flex;flex-wrap:wrap;gap:7px}.category-button{padding:7px 11px;border:1px solid transparent;border-radius:30px;background:transparent;color:#817971;font-size:9px}.category-button.active,.category-button:hover{border-color:#e4d7d0;background:#f3eee8;color:#403c37}.collection-meta{display:flex;align-items:center;gap:18px;color:#968d85;font-size:9px}.collection-meta label{display:flex;align-items:center;gap:6px}.collection-meta select{border:0;background:transparent;color:#625b54;font-size:9px}.store-status{min-height:13px;margin:8px 0 0;color:#55806e;font-size:9px}.product-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:26px 15px}.product-card{min-width:0}.product-image{position:relative;display:grid;place-items:center;aspect-ratio: .81;background:color-mix(in srgb,var(--shirt-bg) 21%,#f3f0eb);overflow:hidden}.product-image:before{position:absolute;content:"";width:76%;height:76%;border:1px solid #fff9;border-radius:50%}.shirt-art{position:relative;z-index:1;width:90%;height:84%;filter:drop-shadow(0 15px 9px #30292317)}.shirt-body{fill:var(--shirt);stroke:#29252118;stroke-width:1}.shirt-neck{fill:none;stroke:#ffffff66;stroke-width:3}.shirt-print{color:#fff9}.color-chip{position:absolute;right:10px;bottom:9px;color:#706961;font-size:7px;letter-spacing:.9px}.product-badge{position:absolute;z-index:2;top:10px;left:10px;padding:5px 7px;background:#fbfaf7;color:#62584f;font-size:7px;letter-spacing:.8px}.product-meta{display:flex;justify-content:space-between;gap:7px;padding-top:11px}.product-meta>div{min-width:0}.product-category{margin:0 0 4px;color:#a0968d;font-size:7px;letter-spacing:.75px;text-transform:uppercase}.product-meta h3{margin:0;color:#39342f;font:500 12px/1.4 var(--serif)}.product-meta>strong{flex:none;padding-top:11px;color:#4f4943;font-size:10px;font-weight:500}.product-buy{display:flex;gap:7px;margin-top:11px}.size-select{width:49px;padding:7px 5px;border:1px solid #e8e1da;background:#fbfaf7;color:#6b625b;font-size:9px}.add-button{display:flex;align-items:center;justify-content:space-between;flex:1;padding:8px 10px;border:1px solid #ded5cc;background:transparent;color:#48423d;text-align:left;font-size:9px;transition:.16s}.add-button:hover{border-color:#413b36;background:#413b36;color:white}.add-button span{font-size:13px}.no-results{grid-column:1/-1;padding:45px 0;color:#89827b;text-align:center}.closing-note{padding:49px 20px 54px;background:#eee7df;text-align:center}.closing-note h2{margin:11px 0 17px;font:500 37px/1.13 var(--serif)}.closing-note>a{display:inline-block;padding-bottom:5px;border-bottom:1px solid #a68f81;font-size:10px}.store-footer{display:flex;align-items:center;gap:25px;padding:22px clamp(20px,7vw,100px);border-top:1px solid var(--line)}.store-footer .store-logo{font-size:14px}.store-footer .store-logo span{font-size:6px}.store-footer p,.store-footer>span:last-child{color:#928980;font-size:8px}.store-footer>span:last-child{margin-left:auto}.bag-backdrop{position:fixed;z-index:8;inset:0;background:#241e1b66}.bag-drawer{position:fixed;z-index:9;top:0;right:0;display:flex;flex-direction:column;width:min(410px,100%);height:100dvh;padding:23px;background:#fbfaf7;box-shadow:-12px 0 44px #1e171717;transform:translateX(110%);transition:transform .22s ease}.bag-drawer.open{transform:translateX(0)}.bag-heading{display:flex;justify-content:space-between;align-items:center;padding-bottom:15px;border-bottom:1px solid var(--line)}.bag-heading h2{margin:5px 0 0;font:500 25px var(--serif)}.bag-heading h2 span{color:#958b82;font:10px var(--sans)}.close-button{width:30px;height:30px;border:1px solid var(--line);border-radius:50%;background:none;color:#504943;font-size:21px}.cart-empty{margin:auto;color:#8b8178;font:italic 14px var(--serif)}.cart-items{flex:1;overflow:auto}.bag-item{display:flex;gap:13px;padding:15px 0;border-bottom:1px solid var(--line)}.bag-item .shirt-art{width:87px;height:95px;flex:none;padding:8px;background:#f0e9e1}.bag-item-info{display:flex;flex:1;flex-direction:column;align-items:flex-start;gap:4px}.bag-item-info small{color:#9a8f86;font-size:7px;letter-spacing:.7px}.bag-item-info strong{font:500 12px var(--serif)}.bag-item-info>span{font-size:10px}.quantity-control{display:flex;align-items:center;gap:10px;margin-top:5px}.quantity-control button{width:22px;height:22px;border:1px solid var(--line);background:transparent;color:#605851}.quantity-control>span{font-size:9px}.quantity-control .remove-item{width:auto;border:0;color:#9b777b;font-size:8px}.bag-summary{padding-top:14px;border-top:1px solid var(--line)}.bag-summary>p:first-child{display:flex;justify-content:space-between;margin:0 0 3px;font-size:11px}.bag-summary small{color:#958b82;font-size:8px}.checkout-button{display:flex;justify-content:space-between;width:100%;margin-top:14px;padding:13px 15px;border:0;background:#302d29;color:white;font-size:10px}.checkout-button:hover{background:#55433e}.checkout-button span{font-size:15px}.demo-payment-note{text-align:center;color:#998f87;font-size:8px}.checkout-modal{width:min(420px,calc(100% - 30px));padding:27px;border:1px solid var(--line);background:#fbfaf7;color:var(--ink)}.checkout-modal::backdrop{background:#241e1b77}.checkout-modal form{display:grid;gap:12px}.checkout-modal .modal-close{justify-self:end}.checkout-modal h2{margin:0;font:500 26px var(--serif)}.checkout-note,.checkout-modal small{margin:0;color:#847a72;font-size:9px;line-height:1.6}.checkout-modal label{display:grid;gap:5px;color:#6a615a;font-size:9px}.checkout-modal input{padding:10px;border:1px solid var(--line);background:white;font-size:10px}.checkout-modal .checkout-button{margin-top:5px}.checkout-modal>form>small{text-align:center}@media(max-width:850px){.product-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.shop-hero{margin-inline:28px}.hero-copy{padding:40px 30px}.store-header{padding-inline:28px}.brand-note{margin-inline:28px}.shop-section{padding-inline:28px}.store-footer{padding-inline:28px}}@media(max-width:600px){.store-header{height:59px;grid-template-columns:1fr auto;padding-inline:16px}.store-nav{display:none}.store-logo{font-size:17px}.shop-hero{grid-template-columns:1fr;margin:0 16px}.hero-copy{padding:35px 25px 26px}.hero-copy h1{font-size:53px}.hero-art{min-height:260px}.hero-garment{width:59%}.hero-sticker{top:12%;right:11%}.brand-note{align-items:flex-start;margin-inline:16px;gap:10px}.brand-note p{font-size:11px}.brand-note>span:last-child{max-width:78px;text-align:right;font-size:6px}.shop-section{padding:47px 16px}.shop-heading{align-items:flex-start;flex-direction:column;gap:15px}.shop-heading h2{font-size:28px}.search-wrap{width:100%}.collection-controls{align-items:flex-start;flex-direction:column;margin-top:19px}.collection-meta{width:100%;justify-content:space-between}.product-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:22px 10px}.product-meta{display:block}.product-meta>strong{display:block;padding-top:4px}.product-meta h3{font-size:11px}.product-buy{gap:5px}.size-select{width:43px}.add-button{padding:8px;font-size:8px}.closing-note{padding:38px 16px}.closing-note h2{font-size:32px}.store-footer{flex-wrap:wrap;gap:10px 18px;padding:17px 16px}.store-footer p{flex:1}.store-footer>span:last-child{width:100%;margin:0}.bag-drawer{padding:18px}.bag-item .shirt-art{width:72px;height:84px}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;transition:none!important}}
'''
    app_logic = '''PRODUCTS = [
    {"id": "tee-01", "name": "Everyday Heavyweight Tee", "category": "Tees", "price": 799},
    {"id": "tee-02", "name": "Studio Boxy T-Shirt", "category": "Tees", "price": 899},
    {"id": "tee-03", "name": "Weekend Graphic Tee", "category": "Graphic tees", "price": 999},
    {"id": "tee-04", "name": "Essential Crew T-Shirt", "category": "Tees", "price": 699},
    {"id": "tee-05", "name": "Relaxed Stripe Tee", "category": "Graphic tees", "price": 949},
    {"id": "tee-06", "name": "After Hours Black Tee", "category": "Tees", "price": 849},
    {"id": "tee-07", "name": "Sunday Club T-Shirt", "category": "Graphic tees", "price": 1099},
    {"id": "tee-08", "name": "Classic White Crew", "category": "Tees", "price": 749},
]

def list_products(category="All", query=""):
    term = query.strip().casefold()
    return [
        product for product in PRODUCTS
        if (category == "All" or product["category"] == category)
        and (not term or term in (product["name"] + " " + product["category"]).casefold())
    ]

def add_to_cart(cart, product_id, size="M"):
    product = next((item for item in PRODUCTS if item["id"] == product_id), None)
    if product is None:
        raise ValueError("Unknown product")
    if size not in {"S", "M", "L", "XL"}:
        raise ValueError("Unsupported size")
    row = next((item for item in cart if item["id"] == product_id and item["size"] == size), None)
    if row:
        row["quantity"] += 1
    else:
        cart.append({"id": product_id, "size": size, "quantity": 1})
    return cart

def cart_subtotal(cart):
    prices = {product["id"]: product["price"] for product in PRODUCTS}
    return sum(prices[row["id"]] * row["quantity"] for row in cart)
'''
    tests = '''import app_logic

def test_storefront_has_a_real_clothing_catalog():
    assert len(app_logic.list_products()) == 8
    assert all("Tee" in item["name"] or "T-Shirt" in item["name"] or "Crew" in item["name"] for item in app_logic.list_products())

def test_category_and_search_filters():
    assert len(app_logic.list_products(category="Tees")) == 5
    assert [item["id"] for item in app_logic.list_products(query="stripe")] == ["tee-05"]

def test_bag_adds_sizes_and_calculates_subtotal():
    bag = []
    app_logic.add_to_cart(bag, "tee-01", "M")
    app_logic.add_to_cart(bag, "tee-01", "M")
    app_logic.add_to_cart(bag, "tee-02", "L")
    assert bag == [{"id": "tee-01", "size": "M", "quantity": 2}, {"id": "tee-02", "size": "L", "quantity": 1}]
    assert app_logic.cart_subtotal(bag) == 2497

def test_bag_rejects_unknown_items_and_sizes():
    for product_id, size in [("unknown", "M"), ("tee-01", "XXL")]:
        try:
            app_logic.add_to_cart([], product_id, size)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid cart item should be rejected")
'''
    dockerfile = '''FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html styles.css app.js favicon.svg /usr/share/nginx/html/
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
'''
    nginx = '''server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;
    server_tokens off;

    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'; form-action 'self'" always;

    location = /health {
        access_log off;
        add_header Content-Type text/plain;
        return 200 "ok";
    }

    location / {
        try_files $uri $uri/ =404;
    }
}
'''
    deployment = f'''# {brand_text} Studio — deployment guide

This bundle contains a responsive, static storefront and a Docker/Nginx production-serving configuration. The shopping bag and checkout form are a **demo only**: no orders or payments are processed.

## Run locally

Open `index.html` in a browser, or serve this folder with any static web server.

## Build and run the production container

Install Docker, then run:

```sh
docker build -t {brand.lower().replace(" ", "-")}-store .
docker run --rm -p 8080:80 {brand.lower().replace(" ", "-")}-store
```

Open `http://localhost:8080`. The `/health` endpoint can be used by a container health check or hosting platform.

## Before accepting real customers

- Connect a trusted payment provider and a server-side order API. Never collect or store card details in this static demo.
- Add inventory, order persistence, shipping/tax rules, refunds, and transactional email.
- Replace sample prices, product copy, sizing, and vector product illustrations with approved brand assets.
- Add privacy/terms/returns policies, contact details, analytics consent, and your verified domain.
- Configure HTTPS, backups, monitoring, and deployment secrets in your hosting provider.

Deploying the container serves this demo storefront; production commerce operations require those integrations and credentials.
'''
    readme = f'''# {brand_text} Studio clothing storefront

A responsive apparel shop demo featuring eight T-shirts, local search and category filters, price sorting, size selection, a working shopping bag with quantity controls, subtotal calculation, and a clearly identified demo checkout. The product illustrations are inline vector artwork, so the preview works offline.

## Preview and test

Open `index.html` in a browser. Run `python -m pytest -q` for catalog, filter, bag, size validation, and subtotal tests.

## Production serving

`Dockerfile`, `nginx.conf`, and `DEPLOYMENT.md` prepare the static storefront for container-based hosting. Checkout is a front-end demonstration only: connect a secure server-side order flow and payment provider before taking real orders.
'''
    return Template("ecommerce-store", {
        "index.html": html_doc,
        "styles.css": styles,
        "app.js": app_js,
        "app_logic.py": app_logic,
        "test_app.py": tests,
        "README.md": readme,
        "Dockerfile": dockerfile,
        "nginx.conf": nginx,
        "DEPLOYMENT.md": deployment,
        "favicon.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#282521"/><path d="m32 8 24 24-24 24L8 32z" fill="none" stroke="#f1d7ce" stroke-width="2"/><text x="32" y="39" text-anchor="middle" fill="#a45a68" font-size="22" font-family="Georgia">N</text></svg>\n',
    })


def _fuzzy_contains(normalized: str, targets: tuple[str, ...], threshold: float = 0.75) -> bool:
    words = re.findall(r"[a-z]+", normalized)
    return any(word == target or SequenceMatcher(None, word, target).ratio() >= threshold for word in words for target in targets)


def select_template(requirement: str) -> Template:
    normalized = requirement.lower()
    if _fuzzy_contains(normalized, ("ecommerce", "fashion", "clothing", "clothes", "apparel", "boutique", "shop", "store", "shirts", "shirt", "tshirts", "tshirt", "tee")):
        return _clothing_store_template(requirement)
    if _fuzzy_contains(normalized, ("calculator", "calculate", "arithmetic", "calc")):
        return _calculator_template()
    if _fuzzy_contains(normalized, ("todo", "task", "checklist", "planner")):
        return _todo_template()
    return _landing_template(requirement)
