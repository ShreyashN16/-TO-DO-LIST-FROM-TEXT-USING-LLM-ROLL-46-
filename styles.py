"""styles.py - custom CSS that gives the Streamlit app its own look."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Instrument+Serif:ital@0;1&display=swap');

:root{
  --ink:#16162a; --muted:#6b6b85; --line:#e6e6f0; --card:#ffffff; --bg:#f6f6fb;
  --brand:#5b5bd6; --brand2:#8e4ec6; --high:#e5484d; --med:#f0a020; --low:#30a46c;
  --high-bg:#fff0f0; --med-bg:#fff7e8; --low-bg:#eaf8f0;
}
html, body, [class*="css"], .stMarkdown, .stTextArea textarea, button, input {
  font-family:'Plus Jakarta Sans', system-ui, sans-serif !important;
}
.block-container{padding-top:1.4rem; max-width:1200px;}
header[data-testid="stHeader"]{background:transparent;}

/* ---------- hero ---------- */
.hero{position:relative; overflow:hidden; border-radius:22px; padding:30px 34px;
  background:
    radial-gradient(1200px 300px at 0% 0%, rgba(142,78,198,.35), transparent 60%),
    radial-gradient(800px 300px at 100% 100%, rgba(91,91,214,.45), transparent 60%),
    linear-gradient(135deg,#17172e 0%,#24245a 100%);
  color:#fff; margin-bottom:18px; box-shadow:0 18px 40px -18px rgba(40,40,110,.55);}
.hero h1{font-family:'Instrument Serif',serif !important; font-weight:400; font-size:3.0rem;
  line-height:1; margin:0 0 6px 0; letter-spacing:-.5px; color:#fff;}
.hero h1 em{font-style:italic; background:linear-gradient(90deg,#c4b5fd,#f9a8d4);
  -webkit-background-clip:text; background-clip:text; color:transparent;}
.hero p{color:#cfd0ff; margin:0; font-size:1.02rem; max-width:640px;}
.hero .pill{display:inline-flex; gap:8px; align-items:center; margin-top:14px; padding:6px 12px;
  border-radius:999px; background:rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.18);
  font-size:.82rem; color:#e9e9ff;}
.hero .dot{width:8px;height:8px;border-radius:50%;background:#46d18a;box-shadow:0 0 0 4px rgba(70,209,138,.2);}
.hero .dot.off{background:#f0a020;box-shadow:0 0 0 4px rgba(240,160,32,.2);}
.hero .steps{position:absolute; right:30px; top:30px; display:flex; gap:8px;}
.hero .step{background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.15); border-radius:12px;
  padding:8px 12px; font-size:.78rem; color:#dcdcff;}
.hero .step b{display:block; color:#fff; font-size:.9rem;}
@media (max-width: 900px){ .hero .steps{display:none;} .hero h1{font-size:2.3rem;} }

/* ---------- section titles ---------- */
.sec{font-weight:800; font-size:1.05rem; color:var(--ink); margin:6px 0 2px 0; letter-spacing:-.2px;}
.sub{color:var(--muted); font-size:.88rem; margin-bottom:8px;}

/* ---------- stat tiles ---------- */
.stats{display:grid; grid-template-columns:repeat(6,1fr); gap:12px; margin:6px 0 14px 0;}
@media (max-width: 900px){ .stats{grid-template-columns:repeat(3,1fr);} }
.stat{background:var(--card); border:1px solid var(--line); border-radius:16px; padding:14px 16px;}
.stat .k{color:var(--muted); font-size:.76rem; font-weight:600; text-transform:uppercase; letter-spacing:.6px;}
.stat .v{font-size:1.7rem; font-weight:800; color:var(--ink); line-height:1.2;}
.stat.hi .v{color:var(--high);} .stat.warn .v{color:var(--med);} .stat.ok .v{color:var(--low);}

.summary{background:linear-gradient(90deg,#efeefe,#f7efff); border:1px solid #dcd8fb; border-radius:14px;
  padding:12px 16px; color:#33336b; font-size:.95rem; margin-bottom:10px;}
.summary b{color:var(--brand);}
.warnbox{background:#fff7e8; border:1px solid #f6d79a; border-radius:12px; padding:10px 14px;
  color:#7a5200; font-size:.88rem; margin-bottom:10px;}

/* ---------- task cards (st.container(key="card_<priority>_<id>")) ---------- */
div[class*="st-key-card_"]{background:var(--card); border:1px solid var(--line); border-radius:14px;
  padding:10px 14px 8px 14px; border-left:5px solid var(--brand); transition:all .15s ease;
  box-shadow:0 1px 2px rgba(20,20,60,.04);}
div[class*="st-key-card_"]:hover{transform:translateY(-1px); box-shadow:0 10px 24px -12px rgba(40,40,110,.35);}
div[class*="st-key-card_High"]{border-left-color:var(--high);}
div[class*="st-key-card_Medium"]{border-left-color:var(--med);}
div[class*="st-key-card_Low"]{border-left-color:var(--low);}
div[class*="st-key-card_"][class*="_done"]{opacity:.55; background:#fafafa;}
div[class*="st-key-card_"] [data-testid="stHorizontalBlock"]{align-items:center;}

.ttl{font-weight:700; font-size:1.0rem; color:var(--ink); line-height:1.35;}
.ttl.done{text-decoration:line-through; color:#9a9ab0;}
.chips{display:flex; flex-wrap:wrap; gap:6px; margin-top:6px;}
.chip{display:inline-flex; align-items:center; gap:4px; font-size:.74rem; font-weight:600; padding:3px 9px;
  border-radius:999px; background:#f1f1f7; color:#4a4a66; border:1px solid #e6e6f0;}
.chip.High{background:var(--high-bg); color:var(--high); border-color:#ffd0d1;}
.chip.Medium{background:var(--med-bg); color:#b06d00; border-color:#fde2b0;}
.chip.Low{background:var(--low-bg); color:var(--low); border-color:#c4ecd5;}
.chip.over{background:#e5484d; color:#fff; border-color:#e5484d;}
.chip.today{background:#16162a; color:#fff; border-color:#16162a;}
.why{color:var(--muted); font-size:.8rem; margin-top:5px;}
.why i{color:#9a9ab0;}
.score{font-weight:800; font-size:1.25rem; text-align:center; color:var(--ink); line-height:1;}
.score small{display:block; font-size:.62rem; color:var(--muted); font-weight:600; letter-spacing:.5px;}

.grouphead{display:flex; align-items:center; gap:10px; margin:16px 0 6px 0; font-weight:800; color:var(--ink);}
.grouphead .bar{flex:1; height:1px; background:var(--line);}
.grouphead .n{font-size:.75rem; font-weight:700; color:var(--muted); background:#efeff6; padding:2px 8px; border-radius:999px;}

/* ---------- eisenhower matrix ---------- */
.matrix{display:grid; grid-template-columns:1fr 1fr; gap:14px;}
.quad{border-radius:18px; padding:14px 16px; min-height:190px; border:1px solid var(--line); background:#fff;}
.quad h4{margin:0 0 2px 0; font-size:1rem; font-weight:800;}
.quad .hint{font-size:.78rem; color:var(--muted); margin-bottom:8px;}
.quad.q1{background:linear-gradient(180deg,#fff1f1,#fff);} .quad.q1 h4{color:var(--high);}
.quad.q2{background:linear-gradient(180deg,#f0efff,#fff);} .quad.q2 h4{color:var(--brand);}
.quad.q3{background:linear-gradient(180deg,#fff7e8,#fff);} .quad.q3 h4{color:#b06d00;}
.quad.q4{background:linear-gradient(180deg,#eef8f2,#fff);} .quad.q4 h4{color:var(--low);}
.qi{background:#fff; border:1px solid var(--line); border-radius:10px; padding:7px 10px; margin-bottom:6px;
  font-size:.86rem; font-weight:600; color:var(--ink); display:flex; justify-content:space-between; gap:8px;}
.qi span{color:var(--muted); font-weight:500; font-size:.76rem; white-space:nowrap;}

/* ---------- plan ---------- */
.slot{display:grid; grid-template-columns:90px 1fr; gap:12px; align-items:stretch; margin-bottom:8px;}
.slot .t{font-weight:700; color:var(--brand); font-size:.85rem; padding-top:10px;}
.slot .b{background:#fff; border:1px solid var(--line); border-left:4px solid var(--brand); border-radius:12px;
  padding:9px 12px; font-weight:600; color:var(--ink);}
.slot .b.High{border-left-color:var(--high);} .slot .b.Medium{border-left-color:var(--med);} .slot .b.Low{border-left-color:var(--low);}
.slot .b span{display:block; font-weight:500; color:var(--muted); font-size:.78rem;}

/* ---------- widgets ---------- */
.stTextArea textarea{border-radius:14px !important; font-size:.95rem !important; line-height:1.55 !important;
  background:#fff !important;}
div.st-key-go button{background:linear-gradient(135deg,#5b5bd6,#8e4ec6) !important; color:#fff !important;
  border:0 !important; border-radius:14px !important; height:3.1rem; width:100%; font-weight:700 !important;
  font-size:1.02rem !important; box-shadow:0 12px 24px -12px rgba(91,91,214,.8);}
div.st-key-go button:hover{filter:brightness(1.07); transform:translateY(-1px);}
.stTabs [data-baseweb="tab-list"]{gap:6px;}
.stTabs [data-baseweb="tab"]{border-radius:10px 10px 0 0; padding:8px 14px; font-weight:600;}
section[data-testid="stSidebar"]{background:#ffffff; border-right:1px solid var(--line);}
.side-brand{font-family:'Instrument Serif',serif; font-size:1.7rem; color:var(--ink); line-height:1;}
.side-brand em{color:var(--brand);}
.empty{border:2px dashed #dcdcec; border-radius:18px; padding:36px; text-align:center; color:var(--muted);}
.empty b{display:block; font-size:1.1rem; color:var(--ink); margin-bottom:4px;}
.foot{color:#9a9ab0; text-align:center; font-size:.78rem; margin-top:30px;}
</style>
"""
