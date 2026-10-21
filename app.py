import os, secrets, sqlite3, hashlib
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, jsonify, request, session, redirect, url_for, render_template_string
import requests
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.getenv('FLASK_SECRET_KEY') or 'local-dev-only-change-this-secret'
TOMTOM_API_KEY = os.getenv('TOMTOM_API_KEY', '').strip()
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '').strip()
STATUSES = ('Received', 'In Progress', 'Resolved', 'Closed')


def db_connect():
    if DATABASE_URL.startswith(('postgres://', 'postgresql://')):
        try:
            import psycopg2
            return 'pg', psycopg2.connect(DATABASE_URL, connect_timeout=10)
        except ImportError as exc:
            raise RuntimeError('Install psycopg2-binary to use PostgreSQL.') from exc
    conn = sqlite3.connect(os.getenv('LOCAL_DB_PATH', 'citymind_issues.db'), timeout=10)
    conn.row_factory = sqlite3.Row
    return 'sqlite', conn


def init_db():
    kind, conn = db_connect()
    try:
        cur = conn.cursor()
        if kind == 'pg':
            cur.execute('''CREATE TABLE IF NOT EXISTS issues (
                id BIGSERIAL PRIMARY KEY, ticket_id VARCHAR(20) UNIQUE NOT NULL,
                lookup_hash VARCHAR(64) NOT NULL, name VARCHAR(120), email VARCHAR(254),
                category VARCHAR(40) NOT NULL, title VARCHAR(160) NOT NULL,
                description TEXT NOT NULL, status VARCHAR(30) NOT NULL DEFAULT 'Received',
                admin_note TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())''')
        else:
            cur.execute('''CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT UNIQUE NOT NULL,
                lookup_hash TEXT NOT NULL, name TEXT, email TEXT, category TEXT NOT NULL,
                title TEXT NOT NULL, description TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Received',
                admin_note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
        conn.commit()
    finally:
        conn.close()


def row_dict(row, kind):
    if kind == 'pg':
        cols = ['id','ticket_id','lookup_hash','name','email','category','title','description','status','admin_note','created_at','updated_at']
        return dict(zip(cols, row))
    return dict(row)


def execute(sql, params=(), fetch=None):
    init_db()
    kind, conn = db_connect()
    try:
        cur = conn.cursor()
        if kind == 'pg':
            sql = sql.replace('?', '%s')
        cur.execute(sql, params)
        result = None
        if fetch == 'one':
            row = cur.fetchone()
            if row is not None:
                if kind == 'pg':
                    # Cursor tuple order is selected by query; use cursor description.
                    result = dict(zip([d[0] for d in cur.description], row))
                else:
                    result = dict(row)
        elif fetch == 'all':
            rows = cur.fetchall()
            result = [dict(zip([d[0] for d in cur.description], r)) if kind == 'pg' else dict(r) for r in rows]
        conn.commit()
        return result
    finally:
        conn.close()


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin_login'))
        return fn(*args, **kwargs)
    return wrapped

@app.get('/')
def index():
    return app.send_static_file('index.html')

@app.get('/api/health')
def health():
    try:
        init_db()
        db_ok = True
    except Exception:
        db_ok = False
    return jsonify({'status': 'ok' if db_ok else 'degraded', 'database_configured': bool(DATABASE_URL), 'database_ok': db_ok, 'tomtom_configured': bool(TOMTOM_API_KEY)})

@app.get('/api/traffic')
def traffic():
    if not TOMTOM_API_KEY:
        return jsonify({'error': 'TOMTOM_API_KEY is not configured.'}), 503
    try:
        lat = float(request.args.get('lat', '')); lon = float(request.args.get('lon', ''))
        if not (-90 <= lat <= 90 and -180 <= lon <= 180): raise ValueError()
    except ValueError:
        return jsonify({'error': 'Provide valid latitude and longitude.'}), 400
    try:
        response = requests.get('https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json', params={'point': f'{lat},{lon}', 'unit': 'KMPH', 'key': TOMTOM_API_KEY}, timeout=15)
        if response.status_code in (401, 403): return jsonify({'error': 'TomTom rejected the key. Check key permissions.'}), 502
        response.raise_for_status(); return jsonify(response.json())
    except requests.RequestException:
        return jsonify({'error': 'Traffic provider request failed.'}), 502

@app.post('/api/issues')
def create_issue():
    data = request.get_json(silent=True) or request.form
    category = str(data.get('category', '')).strip()
    title = str(data.get('title', '')).strip()
    description = str(data.get('description', '')).strip()
    name = str(data.get('name', '')).strip()[:120]
    email = str(data.get('email', '')).strip()[:254]
    if category not in ('Bug', 'Login Problem', 'AI Response', 'Map or Data', 'Suggestion', 'Other'):
        return jsonify({'error': 'Choose a valid issue category.'}), 400
    if not title or len(title) > 160 or len(description) < 10 or len(description) > 5000:
        return jsonify({'error': 'Title is required (max 160 chars); description must be 10–5000 characters.'}), 400
    if email and ('@' not in email or len(email) > 254):
        return jsonify({'error': 'Enter a valid email or leave it blank.'}), 400
    ticket_id = 'CM-' + secrets.token_hex(4).upper()
    lookup_token = secrets.token_urlsafe(24)
    token_hash = hashlib.sha256(lookup_token.encode()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    try:
        execute('INSERT INTO issues (ticket_id, lookup_hash, name, email, category, title, description, status, admin_note, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (ticket_id, token_hash, name, email, category, title, description, 'Received', '', now, now))
    except Exception:
        app.logger.exception('Issue could not be saved')
        return jsonify({'error': 'Issue storage is temporarily unavailable. Please try again later.'}), 503
    return jsonify({'ticket_id': ticket_id, 'lookup_token': lookup_token, 'status': 'Received', 'message': 'Issue submitted. Save your Issue ID and private lookup code to check status later.'}), 201

@app.post('/api/issues/lookup')
def lookup_issue():
    data = request.get_json(silent=True) or request.form
    ticket_id = str(data.get('ticket_id', '')).strip().upper()
    token = str(data.get('lookup_token', '')).strip()
    if not ticket_id or not token:
        return jsonify({'error': 'Enter both the Issue ID and private lookup code.'}), 400
    found = execute('SELECT ticket_id, category, title, status, admin_note, created_at, updated_at, lookup_hash FROM issues WHERE ticket_id = ?', (ticket_id,), 'one')
    if not found or not secrets.compare_digest(found['lookup_hash'], hashlib.sha256(token.encode()).hexdigest()):
        return jsonify({'error': 'Issue not found. Check the Issue ID and private lookup code.'}), 404
    return jsonify({k: found[k] for k in ('ticket_id','category','title','status','admin_note','created_at','updated_at')})

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if not ADMIN_PASSWORD:
            return 'Admin is not configured. Set ADMIN_PASSWORD in Render environment variables.', 503
        supplied = request.form.get('password', '')
        if secrets.compare_digest(supplied, ADMIN_PASSWORD):
            session.clear(); session['is_admin'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template_string(LOGIN_HTML, error='Incorrect password.'), 401
    return render_template_string(LOGIN_HTML, error='')

@app.post('/admin/logout')
def admin_logout():
    session.clear(); return redirect(url_for('admin_login'))

@app.get('/admin')
@admin_required
def admin_dashboard():
    issues = execute('SELECT ticket_id, name, email, category, title, description, status, admin_note, created_at, updated_at FROM issues ORDER BY created_at DESC', fetch='all') or []
    return render_template_string(ADMIN_HTML, issues=issues, statuses=STATUSES)

@app.post('/admin/update')
@admin_required
def admin_update():
    ticket_id = request.form.get('ticket_id', '').strip().upper()
    status = request.form.get('status', '')
    note = request.form.get('admin_note', '').strip()[:2000]
    if status not in STATUSES:
        return 'Invalid status', 400
    now = datetime.now(timezone.utc).isoformat()
    execute('UPDATE issues SET status = ?, admin_note = ?, updated_at = ? WHERE ticket_id = ?', (status, note, now, ticket_id))
    return redirect(url_for('admin_dashboard'))

LOGIN_HTML = '''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>CITYMIND Admin Login</title><style>body{font:16px system-ui;background:#07111f;color:#eef5ff;display:grid;place-items:center;min-height:100vh;margin:0}.box{background:#102037;padding:28px;border:1px solid #29415b;border-radius:16px;width:min(90%,380px)}input,button{width:100%;padding:12px;margin-top:12px;border-radius:8px;border:1px solid #2a4660;background:#13243a;color:#fff;box-sizing:border-box}button{background:#46d9ed;color:#06121f;font-weight:bold}.err{color:#ff929d}</style></head><body><form class="box" method="post"><h2>CITYMIND AI · Admin</h2><p>Sign in to manage submitted issues.</p><div class="err">{{ error }}</div><input type="password" name="password" placeholder="Admin password" required autocomplete="current-password"><button>Sign in</button></form></body></html>'''

ADMIN_HTML = '''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>CITYMIND Issue Admin</title><style>body{font:14px/1.5 system-ui;background:#07111f;color:#eef5ff;margin:0;padding:22px}header{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.muted{color:#93a9c4}.issue{background:#102037;border:1px solid #223650;border-radius:14px;padding:18px;margin:14px 0}.meta{color:#93a9c4;font-size:12px}input,select,textarea,button{font:inherit;color:#eef5ff;background:#13243a;border:1px solid #2a4660;border-radius:8px;padding:9px;margin:4px 0;max-width:100%}textarea{width:min(100%,700px);display:block}button{cursor:pointer;background:#46d9ed;color:#06121f;font-weight:700}.logout{display:inline}</style></head><body><header><div><h1>CITYMIND AI — Issue Admin</h1><p class="muted">Review reports and update their public status.</p></div><form method="post" action="/admin/logout"><button>Log out</button></form></header><p><b>{{ issues|length }}</b> issue(s) submitted</p>{% for i in issues %}<article class="issue"><h2>{{ i.title|e }} <small class="meta">{{ i.ticket_id|e }}</small></h2><p class="meta">{{ i.category|e }} · {{ i.status|e }} · {{ i.created_at|e }}</p><p>{{ i.description|e }}</p><p class="meta">Reporter: {{ i.name or 'Not provided' }} · {{ i.email or 'No email' }}</p><form method="post" action="/admin/update"><input type="hidden" name="ticket_id" value="{{ i.ticket_id|e }}"><label>Status <select name="status">{% for s in statuses %}<option value="{{ s }}" {% if s==i.status %}selected{% endif %}>{{ s }}</option>{% endfor %}</select></label><label>Public update/note<textarea name="admin_note" rows="2" maxlength="2000" placeholder="Optional update visible to the reporter">{{ i.admin_note|e }}</textarea></label><button>Save update</button></form></article>{% else %}<p>No issues yet.</p>{% endfor %}</body></html>'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=False)
