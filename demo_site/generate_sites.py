"""Generates the extra fictional demo websites in demo_site/sites/<slug>/{broken,fixed}/.

Every site is a small multi-page flow (one page per journey step). The "broken"
version has real accessibility bugs picked from BUGS; the "fixed" version has none.
Run:  python demo_site/generate_sites.py
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "sites"

# Bug catalogue (broken version only):
#   trap@N        keyboard focus trapped in a side menu on the page of step N (1-based)
#   divbtn@N      control for step N is a <div onclick> (mouse only)
#   no_outline    focus outline removed      low_contrast  light grey text
#   no_lang       <html> has no lang         no_zoom       pinch-zoom disabled
#   img_alt       image without alt          icon_link     icon-only link, no name
#   small_target  18px tap targets           no_label      form field without label
#   clickable_div <div> used as a button     overflow      page wider than a phone
#   vague_link    "Click here" link          heading_skip  h1 jumps to h4
SITES = [
    dict(slug="streamnest", name="StreamNest", kind="Video streaming", color="#e11d48",
         task="Find the masala dosa cooking video and start playing it",
         steps=["Trending now", "Masala Dosa in 10 Minutes", "Play video"],
         pages=["Watch what India is watching", "Trending now", "Masala Dosa in 10 Minutes"],
         decoys=["Live cricket", "Music videos"], done="Now playing: Masala Dosa in 10 Minutes",
         bugs=["trap@3", "no_outline", "img_alt", "icon_link", "small_target"]),
    dict(slug="mailnest", name="MailNest", kind="Email", color="#2563eb",
         task="Open the inbox, write a new email and send it",
         steps=["Open inbox", "Compose email", "Send email"],
         pages=["Your mail, simple and fast", "Inbox — 3 unread", "New message"],
         decoys=["Starred mail", "Spam folder"], done="Email sent",
         bugs=["divbtn@3", "no_label", "no_outline", "low_contrast"]),
    dict(slug="travelgo", name="TravelGo", kind="Flight booking", color="#0ea5e9",
         task="Search Delhi to Mumbai flights and book the morning flight",
         steps=["Search flights", "Delhi to Mumbai 7:00 AM flight", "Continue to booking"],
         pages=["Fly anywhere in India", "Flight results", "Delhi to Mumbai 7:00 AM flight"],
         decoys=["Hotel deals", "Holiday packages"], done="Booking started — review passenger details",
         bugs=["trap@2", "no_zoom", "small_target", "overflow", "no_lang"]),
    dict(slug="fooddash", name="FoodDash", kind="Food delivery", color="#f97316",
         task="Order paneer tikka from a restaurant and reach checkout",
         steps=["Spice Route Kitchen", "Add paneer tikka", "Go to checkout"],
         pages=["Hot food in 30 minutes", "Spice Route Kitchen", "Your order"],
         decoys=["Pizza places", "Desserts near you"], done="Checkout — confirm your address",
         bugs=["divbtn@2", "img_alt", "clickable_div", "no_outline"]),
    dict(slug="banklite", name="BankLite", kind="Net banking", color="#059669",
         task="Start a money transfer, review it and confirm",
         steps=["Transfer money", "Review transfer", "Confirm transfer"],
         pages=["Banking made light", "Transfer money", "Review transfer"],
         decoys=["Fixed deposits", "Credit card offers"], done="Transfer confirmed (demo — no money moved)",
         bugs=["no_label", "low_contrast", "vague_link", "heading_skip"]),
    dict(slug="learnhub", name="LearnHub", kind="Online courses", color="#7c3aed",
         task="Find the Python basics course and enroll for free",
         steps=["Browse courses", "Python Basics for Beginners", "Enroll for free"],
         pages=["Learn new skills every day", "All courses", "Python Basics for Beginners"],
         decoys=["Teach on LearnHub", "Certificates"], done="You are enrolled in Python Basics",
         bugs=["trap@1", "no_outline", "icon_link", "img_alt"]),
    dict(slug="healthplus", name="HealthPlus", kind="Doctor appointments", color="#0d9488",
         task="Find a general physician and book an appointment",
         steps=["Find a doctor", "Dr. Kavya Mehta", "Book appointment"],
         pages=["Care when you need it", "Doctors near you", "Dr. Kavya Mehta, General Physician"],
         decoys=["Lab tests", "Medicine delivery"], done="Appointment booked for tomorrow, 10:30 AM",
         bugs=["divbtn@3", "small_target", "no_zoom", "low_contrast"]),
    dict(slug="newsdaily", name="NewsDaily", kind="News", color="#475569",
         task="Open the technology section and read the top story",
         steps=["Technology", "Chip makers race to build cheaper AI", "Read full story"],
         pages=["News that matters", "Technology", "Chip makers race to build cheaper AI"],
         decoys=["Sports", "Business"], done="Full story",
         bugs=["vague_link", "heading_skip", "img_alt", "low_contrast"]),
    dict(slug="railyatra", name="RailYatra", kind="Train tickets", color="#b45309",
         task="Search trains from Delhi to Jaipur and book a seat",
         steps=["Search trains", "Shatabdi Express 12015", "Book seat"],
         pages=["Book train tickets in seconds", "Trains: Delhi to Jaipur", "Shatabdi Express 12015"],
         decoys=["PNR status", "Cancel ticket"], done="Seat booked — coach C2, seat 14",
         bugs=["trap@2", "no_label", "overflow", "small_target", "no_outline"]),
    dict(slug="citycab", name="CityCab", kind="Ride booking", color="#facc15",
         task="Book a ride, choose a car and confirm it",
         steps=["Book a ride", "Choose Mini car", "Confirm ride"],
         pages=["Rides in minutes", "Where to?", "Choose your car"],
         decoys=["Ride history", "Offers for you"], done="Ride confirmed — driver arriving in 4 min",
         bugs=["divbtn@2", "icon_link", "small_target", "no_zoom"]),
    dict(slug="jobbridge", name="JobBridge", kind="Job portal", color="#4f46e5",
         task="Find a frontend developer job and submit an application",
         steps=["Search jobs", "Frontend Developer at Nimbus Labs", "Apply now"],
         pages=["Find work you love", "Jobs for you", "Frontend Developer at Nimbus Labs"],
         decoys=["Salary guide", "Company reviews"], done="Application submitted",
         bugs=["no_label", "heading_skip", "no_outline"]),
    dict(slug="homefinder", name="HomeFinder", kind="Rental homes", color="#db2777",
         task="Find a 2BHK flat in Pune and contact the owner",
         steps=["Rent a home", "2BHK flat in Baner Pune", "Contact owner"],
         pages=["Find your next home", "Homes for rent", "2BHK flat in Baner Pune"],
         decoys=["Buy property", "Home loans"], done="Message sent to the owner",
         bugs=["trap@3", "img_alt", "overflow", "clickable_div"]),
    dict(slug="govserve", name="GovServe", kind="Government services", color="#1d4ed8",
         task="Start a ration card application and submit it",
         steps=["Citizen services", "Apply for ration card", "Submit application"],
         pages=["Government services online", "Citizen services", "Apply for ration card"],
         decoys=["Track application", "Download forms"], done="Application submitted — reference RC-20491",
         bugs=["divbtn@3", "no_label", "no_lang", "low_contrast", "vague_link"]),
    dict(slug="musicwave", name="MusicWave", kind="Music streaming", color="#16a34a",
         task="Open the lo-fi study playlist and play it",
         steps=["Your playlists", "Lo-fi Study Beats", "Play playlist"],
         pages=["Music for every mood", "Your playlists", "Lo-fi Study Beats"],
         decoys=["Podcasts", "New releases"], done="Playing Lo-fi Study Beats",
         bugs=["icon_link", "small_target", "no_outline"]),
    dict(slug="fittrack", name="FitTrack", kind="Fitness app", color="#ea580c",
         task="Pick the 30-day yoga plan and start it",
         steps=["Workout plans", "30-Day Yoga Journey", "Start plan"],
         pages=["Get fit, one day at a time", "Workout plans", "30-Day Yoga Journey"],
         decoys=["Diet tips", "Step tracker"], done="Day 1 of 30 started",
         bugs=["trap@1", "low_contrast", "no_zoom"]),
    dict(slug="payquick", name="PayQuick", kind="Bill payments", color="#0891b2",
         task="Pay the electricity bill",
         steps=["Pay bills", "Electricity bill", "Pay now"],
         pages=["Pay any bill in one tap", "Pay bills", "Electricity bill — due 28 Oct"],
         decoys=["Mobile recharge", "Rewards"], done="Payment successful (demo — no money moved)",
         bugs=["divbtn@3", "clickable_div", "small_target", "no_outline"]),
    dict(slug="eventbox", name="EventBox", kind="Event tickets", color="#c026d3",
         task="Find the Delhi tech meetup and get a ticket",
         steps=["Upcoming events", "Delhi Tech Meetup", "Get tickets"],
         pages=["Things to do this weekend", "Upcoming events", "Delhi Tech Meetup"],
         decoys=["Comedy shows", "Concerts"], done="Ticket reserved — see you there",
         bugs=["img_alt", "vague_link", "heading_skip"]),
    dict(slug="greengrocer", name="GreenGrocer", kind="Grocery delivery", color="#65a30d",
         task="Add mangoes to the basket and go to checkout",
         steps=["Fresh fruits", "Alphonso Mangoes 1 kg", "Add to basket", "Checkout now"],
         pages=["Fresh groceries at your door", "Fresh fruits", "Alphonso Mangoes 1 kg", "Your basket"],
         decoys=["Vegetables", "Dairy and eggs"], done="Checkout — choose a delivery slot",
         bugs=["trap@3", "img_alt", "no_label", "small_target", "no_outline"]),
    dict(slug="ticketflix", name="TicketFlix", kind="Movie tickets", color="#dc2626",
         task="Book seats for a movie show",
         steps=["Now showing", "Space Odyssey 2077", "Select seats", "Proceed to pay"],
         pages=["Movies near you", "Now showing", "Space Odyssey 2077", "Pick your seats"],
         decoys=["Coming soon", "Gift cards"], done="Seats selected — complete payment",
         bugs=["divbtn@4", "overflow", "low_contrast", "icon_link"]),
    dict(slug="socialcircle", name="SocialCircle", kind="Social network", color="#0284c7",
         task="Open messages and send a message to Riya",
         steps=["Messages", "Chat with Riya", "Send message"],
         pages=["Stay close to friends", "Messages", "Chat with Riya"],
         decoys=["Photos", "Groups"], done="Message sent to Riya",
         bugs=["no_label", "icon_link", "no_zoom", "heading_skip"]),
]

ICON = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"%s>'
        '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/></svg>')
IMG = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10'/%3E"


def has(bugs, name, step=None):
    if step is None:
        return name in bugs
    return f"{name}@{step}" in bugs


def css(s, fixed, bugs):
    c = s["color"]
    b = (lambda n: (not fixed) and n in bugs)
    return f"""
*{{box-sizing:border-box}} body{{margin:0;font-family:system-ui,Segoe UI,Arial,sans-serif;color:#111827;background:#f8fafc}}
{'*:focus{outline:none}' if b('no_outline') else ':focus-visible{outline:3px solid #1d4ed8;outline-offset:2px;border-radius:6px}'}
.skip-link{{position:absolute;left:-999px;top:8px;background:#111827;color:#fff;padding:8px 12px;border-radius:6px}}
.skip-link:focus{{left:8px;z-index:10}}
.sr-only{{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}}
header{{display:flex;align-items:center;gap:16px;padding:12px 24px;background:#fff;border-bottom:3px solid {c}}}
.logo{{font-weight:800;font-size:20px;color:#111827;text-decoration:none}} .logo span{{color:{c if not fixed else '#111827'};{'' if not fixed else 'border-bottom:3px solid '+c}}}
.icon-link{{margin-left:auto;display:inline-flex;align-items:center;justify-content:center;gap:6px;color:#111827;text-decoration:none;
  {'width:18px;height:18px' if b('small_target') else 'min-width:44px;min-height:44px;padding:8px 12px;border:1px solid #d1d5db;border-radius:8px'}}}
.icon-link svg{{width:18px;height:18px}}
.layout{{display:flex;gap:24px;padding:24px;max-width:1100px;margin:auto;flex-wrap:wrap}}
aside{{width:200px;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:12px}}
aside a{{display:block;padding:10px;color:#111827;text-decoration:none;border-radius:8px}}
main{{flex:1;min-width:260px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px}}
.card a{{color:#1d4ed8;font-weight:600;text-decoration:none}}
.thumb{{width:100%;height:140px;border-radius:8px;background:linear-gradient(135deg,{c}33,{c}11);display:block}}
.note{{color:{'#c4c4c4' if b('low_contrast') else '#4b5563'};font-size:13px}}
.btn{{display:inline-block;background:{c};color:{'#111827' if c in ('#facc15','#65a30d','#16a34a','#ea580c','#f97316') else '#fff'};border:0;padding:12px 18px;border-radius:10px;font-size:16px;font-weight:600;cursor:pointer;text-decoration:none}}
.help{{display:inline-block;margin-top:12px;padding:8px 12px;border:1px solid #d1d5db;border-radius:8px;cursor:pointer;background:#fff;font:inherit}}
.banner{{{'width:1100px' if b('overflow') else 'max-width:100%'};background:{c}22;border-radius:10px;padding:12px;margin:12px 0}}
form.sub{{margin-top:16px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
form.sub input{{padding:10px;border:1px solid #d1d5db;border-radius:8px}} form.sub button{{padding:10px 16px;border-radius:8px;border:1px solid #d1d5db;background:#fff;font:inherit;cursor:pointer}}
footer{{padding:24px;text-align:center;color:#6b7280}}
"""


def head(s, title, fixed, bugs):
    lang = ' lang="en"' if (fixed or "no_lang" not in bugs) else ""
    vp = ("width=device-width, initial-scale=1" if (fixed or "no_zoom" not in bugs)
          else "width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no")
    return (f'<!doctype html>\n<html{lang}>\n<head><meta charset="utf-8"><meta name="viewport" content="{vp}">\n'
            f'<title>{title} – {s["name"]}</title><link rel="stylesheet" href="style.css"></head>\n<body>\n')


def header(s, fixed, bugs):
    brand = f'<a class="logo" href="index.html">{s["name"][:-4]}<span>{s["name"][-4:]}</span></a>'
    if fixed or "icon_link" not in bugs:
        icon = f'<a class="icon-link" href="index.html" aria-label="Your profile">{ICON % " aria-hidden=\"true\""}<span>Profile</span></a>'
    else:
        icon = f'<a class="icon-link" href="index.html">{ICON % ""}</a>'
    skip = '<a class="skip-link" href="#main">Skip to main content</a>\n' if fixed else ""
    return f"{skip}<header>{brand}{icon}</header>\n"


def side_menu(s, fixed, trap):
    items = "".join(f'<a href="#">{t}</a>' for t in ("Overview", "Popular", "Saved", "Settings"))
    nav = f'<aside><nav id="side-menu" aria-label="Section menu">{items}</nav></aside>\n'
    script = ""
    if trap and not fixed:
        script = """<script>
// BUG (on purpose): Tab and Shift+Tab wrap inside this menu, Escape does nothing.
(function(){var m=document.getElementById('side-menu'),it=[].slice.call(m.querySelectorAll('a'));
m.addEventListener('keydown',function(e){if(e.key==='Tab'){e.preventDefault();var i=it.indexOf(document.activeElement);
var n=e.shiftKey?(i-1+it.length)%it.length:(i+1)%it.length;it[n].focus();}});})();
</script>
"""
    return nav, script


def control(label, href, fixed, div_bug):
    if div_bug and not fixed:
        return f'<div class="btn" style="cursor:pointer" onclick="location.href=\'{href}\'">{label}</div>'
    return f'<a class="btn" href="{href}">{label}</a>'


def extras(s, fixed, bugs, page_i):
    out = ""
    b = (lambda n: (not fixed) and n in bugs)
    if page_i == 0:
        out += '<div class="banner">' + ("Festive offers are live this week." if True else "") + "</div>\n"
        if b("vague_link"):
            out += '<p>Want weekly updates? <a href="#">Click here</a></p>\n'
        else:
            out += f'<p><a href="#">Get weekly updates from {s["name"]}</a></p>\n'
        if b("no_label"):
            out += '<form class="sub" onsubmit="return false"><input type="email"><button type="submit">Subscribe</button></form>\n'
        else:
            out += ('<form class="sub" onsubmit="return false"><label for="em">Email for updates</label>'
                    '<input id="em" type="email"><button type="submit">Subscribe</button></form>\n')
    if page_i == 1:
        if b("clickable_div"):
            out += '<div class="help" onclick="this.textContent=\'Our team will call you back.\'">Need assistance?</div>\n'
        else:
            out += '<button type="button" class="help" onclick="this.textContent=\'Our team will call you back.\'">Need assistance?</button>\n'
    return out


def page(s, i, fixed, bugs):
    steps, pages = s["steps"], s["pages"]
    n = len(steps)
    href = "done.html" if i == n - 1 else f"p{i + 1}.html"
    name = "index.html" if i == 0 else f"p{i}.html"
    step_no = i + 1
    trap = has(bugs, "trap", step_no)
    div_bug = has(bugs, "divbtn", step_no)
    h_sub = "h4" if ((not fixed) and "heading_skip" in bugs) else "h2"
    alt = f' alt="{pages[i]}"' if (fixed or "img_alt" not in bugs) else ""
    body = head(s, pages[i], fixed, bugs) + header(s, fixed, bugs) + '<div class="layout">\n'
    nav, script = side_menu(s, fixed, trap)
    if trap or i == 1:
        body += nav
    body += f'<main id="main">\n<h1>{pages[i]}</h1>\n<p class="note">{s["kind"]} · demo website for ACCESSPATH testing.</p>\n'
    if i == 0:
        body += f'<img class="thumb"{alt} src="{IMG}">\n'
        cards = [steps[0]] + s["decoys"]
        body += '<div class="grid">' + "".join(
            f'<div class="card"><{h_sub}><a href="{href if c == steps[0] else "#"}">{c}</a></{h_sub}></div>'
            if c != steps[0] or not div_bug else
            f'<div class="card"><{h_sub}>{control(c, href, fixed, True)}</{h_sub}></div>'
            for c in cards) + "</div>\n"
    else:
        body += f'<{h_sub}>Details</{h_sub}>\n<p>Everything you need is on this page.</p>\n<p>{control(steps[i], href, fixed, div_bug)}</p>\n'
    body += extras(s, fixed, bugs, i)
    body += f'</main></div>\n<footer>© {s["name"]} — fictional demo site ({"fixed" if fixed else "broken"} version)</footer>\n'
    body += script + "</body></html>\n"
    return name, body


def done_page(s, fixed, bugs):
    return head(s, "Done", fixed, bugs) + header(s, fixed, bugs) + (
        f'<div class="layout"><main id="main"><h1>{s["done"]}</h1>'
        f'<p><a href="index.html">Back to start</a></p></main></div></body></html>\n')


def build():
    if ROOT.exists():
        shutil.rmtree(ROOT)
    meta = []
    for s in SITES:
        assert len(s["steps"]) == len(s["pages"]), s["slug"]
        for fixed in (False, True):
            d = ROOT / s["slug"] / ("fixed" if fixed else "broken")
            d.mkdir(parents=True)
            bugs = s["bugs"]
            (d / "style.css").write_text(css(s, fixed, bugs).strip() + "\n", encoding="utf-8")
            for i in range(len(s["steps"])):
                name, html = page(s, i, fixed, bugs)
                (d / name).write_text(html, encoding="utf-8")
            (d / "done.html").write_text(done_page(s, fixed, bugs), encoding="utf-8")
        meta.append({"slug": s["slug"], "name": s["name"], "kind": s["kind"], "task": s["task"],
                     "steps": " > ".join(s["steps"]), "bugs": s["bugs"]})
    (ROOT / "sites.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"built {len(SITES)} sites in {ROOT}")


if __name__ == "__main__":
    build()
