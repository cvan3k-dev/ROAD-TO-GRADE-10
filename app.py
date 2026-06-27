from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
import random
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'road_to_grade10.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
CORS(app)

# ============================================================
# MODELS
# ============================================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    
    # Thông tin chung
    level = db.Column(db.Integer, default=1)
    xp = db.Column(db.Integer, default=0)
    coins = db.Column(db.Integer, default=0)
    streak = db.Column(db.Integer, default=0)
    rank = db.Column(db.String(50), default='Tân binh')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    achievements = db.Column(db.Text, default='[]')
    is_admin = db.Column(db.Boolean, default=False)  # Thêm trường admin
    
    # ===== CHẾ ĐỘ NORMAL =====
    normal_mode_best = db.Column(db.Integer, default=0)
    normal_checkpoint = db.Column(db.Integer, default=0)
    normal_hp = db.Column(db.Integer, default=100)
    normal_max_hp = db.Column(db.Integer, default=100)
    
    # ===== CHẾ ĐỘ SURVIVAL =====
    survival_high_score = db.Column(db.Integer, default=0)
    survival_current_floor = db.Column(db.Integer, default=1)
    survival_hp = db.Column(db.Integer, default=100)
    survival_max_hp = db.Column(db.Integer, default=100)
    survival_bosses_killed = db.Column(db.Integer, default=0)

class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    condition = db.Column(db.String(100))
    price = db.Column(db.Integer, default=0)

class UserAchievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id'), nullable=False)
    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow)

class ShopItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    price = db.Column(db.Integer, default=100)
    category = db.Column(db.String(50), default='title')

class UserShopItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('shop_item.id'), nullable=False)
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)

# ===== MODEL CÂU HỎI SINH TỒN =====
class SurvivalQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text, nullable=False)  # Lưu JSON: ["A", "B", "C", "D"]
    correct_answer = db.Column(db.Integer, nullable=False)
    floor_level = db.Column(db.Integer, default=1)
    difficulty = db.Column(db.Integer, default=1)  # 1=Dễ, 2=Trung, 3=Khó
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============================================================
# FILTER TÙY CHỈNH
# ============================================================

@app.template_filter('fromjson')
def fromjson_filter(value):
    if value:
        try:
            return json.loads(value)
        except:
            return []
    return []

@app.template_filter('json')
def json_filter(value):
    return json.dumps(value)

# ============================================================
# KHỞI TẠO DATABASE
# ============================================================

with app.app_context():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db.create_all()
    
    # Tạo admin (nếu chưa có)
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            level=10,
            xp=5000,
            coins=1000,
            rank='Huyền thoại',
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Đã tạo admin: admin / admin123")
    
    # Tạo thành tích mẫu
    if Achievement.query.count() == 0:
        achievements = [
            {'name': 'Người mới', 'description': 'Hoàn thành Level 1', 'icon': '🌱', 'condition': 'level >= 1', 'price': 0},
            {'name': 'Chiến binh', 'description': 'Đạt Level 5', 'icon': '⚔️', 'condition': 'level >= 5', 'price': 50},
            {'name': 'Hiệp sĩ', 'description': 'Đạt Level 10', 'icon': '🛡️', 'condition': 'level >= 10', 'price': 100},
            {'name': 'Bậc thầy ngoại ngữ', 'description': 'Tiêu diệt 20 Boss', 'icon': '📚', 'condition': 'normal_mode_best >= 20', 'price': 200},
            {'name': 'Chiến binh anh ngữ', 'description': 'Tiêu diệt 50 Boss', 'icon': '🏅', 'condition': 'normal_mode_best >= 50', 'price': 500},
            {'name': 'Huyền thoại sống', 'description': 'Tiêu diệt 100 Boss', 'icon': '👑', 'condition': 'normal_mode_best >= 100', 'price': 1000},
        ]
        for a in achievements:
            db.session.add(Achievement(**a))
        db.session.commit()
        print("✅ Đã tạo thành tích mẫu")
    
    # Tạo shop
    if ShopItem.query.count() == 0:
        shop_items = [
            {'name': 'Danh hiệu Bậc thầy', 'description': 'Danh hiệu Bậc thầy ngoại ngữ', 'icon': '📚', 'price': 200, 'category': 'title'},
            {'name': 'Danh hiệu Chiến binh', 'description': 'Danh hiệu Chiến binh anh ngữ', 'icon': '🏅', 'price': 500, 'category': 'title'},
            {'name': 'Danh hiệu Huyền thoại', 'description': 'Danh hiệu Huyền thoại sống', 'icon': '👑', 'price': 1000, 'category': 'title'},
            {'name': 'Hồi sinh tức thì', 'description': 'Hồi sinh ngay tại checkpoint', 'icon': '💚', 'price': 50, 'category': 'consumable'},
        ]
        for item in shop_items:
            db.session.add(ShopItem(**item))
        db.session.commit()
        print("✅ Đã tạo shop items mẫu")

# ============================================================
# HÀM HỖ TRỢ
# ============================================================

def get_levels():
    return [
        {'id': 1, 'name': 'Forest of Vocabulary', 'icon': '🌲', 'boss': 'Goblin'},
        {'id': 2, 'name': 'Grammar Cave', 'icon': '🕳️', 'boss': 'Grammar Troll'},
        {'id': 3, 'name': 'Reading Tower', 'icon': '🏰', 'boss': 'Librarian'},
        {'id': 4, 'name': 'Error City', 'icon': '🏙️', 'boss': 'Bug King'},
        {'id': 5, 'name': 'Vocabulary Maze', 'icon': '🌀', 'boss': 'Maze Minotaur'},
        {'id': 6, 'name': 'Passive Voice Boss', 'icon': '👹', 'boss': 'Passive Demon'},
        {'id': 7, 'name': 'Relative Clause Dungeon', 'icon': '⚔️', 'boss': 'Clause Knight'},
        {'id': 8, 'name': 'Speed Run', 'icon': '💨', 'boss': 'Speed Demon'},
        {'id': 9, 'name': 'Survival Mode', 'icon': '🛡️', 'boss': 'Survival Wraith'},
        {'id': 10, 'name': 'Exam Castle', 'icon': '🏯', 'boss': 'The Exam Lord'},
    ]

def calculate_rank(level):
    if level >= 10: return 'Huyền thoại'
    if level >= 8: return 'Hiệp sĩ'
    if level >= 5: return 'Chiến binh'
    if level >= 3: return 'Nhà thám hiểm'
    return 'Tân binh'

def check_achievements(user_id):
    user = User.query.get(user_id)
    if not user: return
    current = json.loads(user.achievements) if user.achievements else []
    all_ach = Achievement.query.all()
    new_achievements = []
    for ach in all_ach:
        ach_id = f'ach_{ach.id}'
        if ach_id in current: continue
        condition = ach.condition
        if condition.startswith('level >= '):
            req_level = int(condition.split('>=')[1].strip())
            if user.level >= req_level:
                new_achievements.append(ach_id)
                ua = UserAchievement(user_id=user.id, achievement_id=ach.id)
                db.session.add(ua)
        elif condition.startswith('normal_mode_best >= '):
            req = int(condition.split('>=')[1].strip())
            if user.normal_mode_best >= req:
                new_achievements.append(ach_id)
                ua = UserAchievement(user_id=user.id, achievement_id=ach.id)
                db.session.add(ua)
    if new_achievements:
        user.achievements = json.dumps(list(set(current + new_achievements)))
        db.session.commit()

def get_questions(level_id):
    questions_pool = {
        1: [
            {'q': 'Từ nào có nghĩa là "mèo"?', 'options': ['Dog', 'Cat', 'Bird', 'Fish'], 'a': 1},
            {'q': 'Từ nào là màu sắc?', 'options': ['Red', 'Table', 'Run', 'Happy'], 'a': 0},
            {'q': '"Apple" có nghĩa là gì?', 'options': ['Quả táo', 'Quả cam', 'Quả chuối', 'Quả nho'], 'a': 0},
            {'q': 'Từ nào là động vật?', 'options': ['Elephant', 'Table', 'Happy', 'Run'], 'a': 0},
            {'q': 'Chữ cái nào là nguyên âm?', 'options': ['B', 'C', 'A', 'D'], 'a': 2},
        ],
        # ... (giữ nguyên các câu hỏi khác)
    }
    return questions_pool.get(level_id, questions_pool[1])

# ============================================================
# ROUTES USER
# ============================================================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    leaderboard = User.query.order_by(User.xp.desc()).limit(10).all()
    all_ach = Achievement.query.all()
    return render_template('home.html', user=user, leaderboard=leaderboard, all_ach=all_ach)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('home'))
        return render_template('login.html', error='Sai tên đăng nhập hoặc mật khẩu!')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        if password != confirm:
            return render_template('register.html', error='Mật khẩu không khớp!')
        if User.query.filter_by(username=username).first():
            return render_template('register.html', error='Tên đăng nhập đã tồn tại!')
        user = User(username=username, password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('profile.html', user=user)

@app.route('/roadmap')
def roadmap():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    levels = get_levels()
    return render_template('roadmap.html', user=user, levels=levels)

@app.route('/achievement')
def achievement():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    check_achievements(user.id)
    user = User.query.get(session['user_id'])
    unlocked = json.loads(user.achievements) if user.achievements else []
    all_ach = Achievement.query.all()
    return render_template('achievement.html', user=user, all_ach=all_ach, unlocked=unlocked)

@app.route('/shop')
def shop():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    shop_items = ShopItem.query.all()
    purchased = UserShopItem.query.filter_by(user_id=user.id).all()
    purchased_ids = [p.item_id for p in purchased]
    return render_template('shop.html', user=user, shop_items=shop_items, purchased_ids=purchased_ids)

@app.route('/leaderboard')
def leaderboard():
    users = User.query.order_by(User.xp.desc()).limit(20).all()
    survival_users = User.query.order_by(User.survival_high_score.desc()).limit(20).all()
    return render_template('leaderboard.html', users=users, survival_users=survival_users)

@app.route('/shop/buy/<int:item_id>', methods=['POST'])
def buy_item(item_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Chưa đăng nhập!'}), 401
    user = User.query.get(session['user_id'])
    item = ShopItem.query.get(item_id)
    if not item:
        return jsonify({'error': 'Item không tồn tại!'}), 404
    if user.coins < item.price:
        return jsonify({'error': 'Không đủ coin!'}), 400
    existing = UserShopItem.query.filter_by(user_id=user.id, item_id=item_id).first()
    if existing:
        return jsonify({'error': 'Đã mua item này rồi!'}), 400
    user.coins -= item.price
    user_shop = UserShopItem(user_id=user.id, item_id=item_id)
    db.session.add(user_shop)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Đã mua {item.name}!'})

@app.route('/game/<int:level_id>')
def game(level_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    levels = get_levels()
    level = next((l for l in levels if l['id'] == level_id), None)
    if not level:
        return "Level không tồn tại!", 404
    questions = get_questions(level_id)
    selected = random.sample(questions, min(5, len(questions)))
    return render_template('game.html', user=user, level=level, questions=selected, mode='normal')

@app.route('/game/survival')
def survival_game():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('game_survival.html', user=user)

# ============================================================
# API
# ============================================================

@app.route('/api/attack', methods=['POST'])
def attack():
    if 'user_id' not in session:
        return jsonify({'error': 'Chưa đăng nhập!'}), 401
    data = request.json
    level_id = data.get('level_id')
    answer = data.get('answer')
    question_index = data.get('question_index', 0)
    mode = data.get('mode', 'normal')
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User không tồn tại!'}), 404
    
    questions = get_questions(level_id)
    if question_index < len(questions):
        q = questions[question_index]
        correct = q['a']
    else:
        return jsonify({'error': 'Hết câu hỏi!'}), 400
    
    is_correct = (answer == correct)
    
    if is_correct:
        xp_gain = 20 + level_id * 5
        user.xp += xp_gain
        user.coins += 5
        new_level = min(10, user.xp // 200 + 1)
        if new_level > user.level:
            user.level = new_level
            user.rank = calculate_rank(new_level)
        db.session.commit()
        check_achievements(user.id)
        return jsonify({
            'correct': True,
            'message': f'⚔️ Chính xác! +{xp_gain} XP, +5 Coin!',
            'xp': user.xp,
            'level': user.level,
            'coins': user.coins,
            'damage': 20 + level_id * 5,
            'boss_hp_left': max(0, 100 - (question_index + 1) * 25)
        })
    else:
        return jsonify({
            'correct': False,
            'message': '❌ Sai rồi!',
            'damage': 10 + level_id * 2,
            'player_hp': max(0, 100 - (question_index + 1) * 20)
        })

@app.route('/api/survival/question')
def survival_question():
    floor = request.args.get('floor', 1, type=int)
    # Lấy câu hỏi từ database theo tầng
    questions = SurvivalQuestion.query.filter_by(floor_level=floor).all()
    if not questions:
        # Fallback: dùng câu hỏi mặc định
        level_id = random.randint(1, 10)
        pool = get_questions(level_id)
        q = random.choice(pool)
        return jsonify({
            'question': q['q'],
            'options': q['options'],
            'correct_answer': q['a']
        })
    q = random.choice(questions)
    return jsonify({
        'id': q.id,
        'question': q.question,
        'options': json.loads(q.options),
        'correct_answer': q.correct_answer
    })

@app.route('/api/survival/floor', methods=['POST'])
def survival_floor():
    if 'user_id' not in session:
        return jsonify({'error': 'Chưa đăng nhập!'}), 401
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User không tồn tại!'}), 404
    
    user.survival_current_floor += 1
    user.survival_bosses_killed += 1
    if user.survival_current_floor > user.survival_high_score:
        user.survival_high_score = user.survival_current_floor
    user.coins += 10
    db.session.commit()
    
    return jsonify({
        'success': True,
        'floor': user.survival_current_floor,
        'high_score': user.survival_high_score,
        'coins': user.coins
    })

@app.route('/api/survival/end', methods=['POST'])
def survival_end():
    if 'user_id' not in session:
        return jsonify({'error': 'Chưa đăng nhập!'}), 401
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User không tồn tại!'}), 404
    # Lưu high score
    if user.survival_bosses_killed > user.survival_high_score:
        user.survival_high_score = user.survival_bosses_killed
    db.session.commit()
    return jsonify({'success': True, 'high_score': user.survival_high_score})

@app.route('/api/revive', methods=['POST'])
def revive():
    if 'user_id' not in session:
        return jsonify({'error': 'Chưa đăng nhập!'}), 401
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User không tồn tại!'}), 404
    if user.coins >= 50:
        user.coins -= 50
        user.normal_hp = 100
        db.session.commit()
        return jsonify({'success': True, 'message': 'Hồi sinh thành công! -50 Coin'})
    else:
        return jsonify({'error': 'Không đủ coin!'}), 400

@app.route('/api/normal/end', methods=['POST'])
def normal_end():
    if 'user_id' not in session:
        return jsonify({'error': 'Chưa đăng nhập!'}), 401
    data = request.json
    bosses_killed = data.get('bosses_killed', 0)
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User không tồn tại!'}), 404
    if bosses_killed > user.normal_mode_best:
        user.normal_mode_best = bosses_killed
    db.session.commit()
    check_achievements(user.id)
    return jsonify({'success': True, 'message': f'Đã lưu tiến độ Normal! Boss tiêu diệt: {bosses_killed}'})

# ============================================================
# ADMIN (RIÊNG BIỆT, KHÔNG CÓ TRÊN TRANG CHỦ)
# ============================================================

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template('admin_login.html', error='Sai tên đăng nhập hoặc mật khẩu!')
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    users = User.query.all()
    total_users = len(users)
    total_xp = sum(u.xp for u in users)
    avg_level = round(sum(u.level for u in users) / total_users, 1) if total_users > 0 else 0
    return render_template('admin_dashboard.html', 
        users=users, total_users=total_users, total_xp=total_xp, avg_level=avg_level)

@app.route('/admin/users')
def admin_users():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/survival-questions')
def admin_survival_questions():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    questions = SurvivalQuestion.query.order_by(SurvivalQuestion.floor_level).all()
    return render_template('admin_survival_questions.html', questions=questions)

@app.route('/api/admin/survival-questions', methods=['GET', 'POST'])
def api_admin_survival_questions():
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    if request.method == 'GET':
        questions = SurvivalQuestion.query.all()
        return jsonify([{
            'id': q.id,
            'question': q.question,
            'options': json.loads(q.options),
            'correct_answer': q.correct_answer,
            'floor_level': q.floor_level,
            'difficulty': q.difficulty
        } for q in questions])
    
    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Dữ liệu không hợp lệ'}), 400
        
        try:
            q = SurvivalQuestion(
                question=data['question'],
                options=json.dumps(data['options']),
                correct_answer=int(data['correct_answer']),
                floor_level=int(data.get('floor_level', 1)),
                difficulty=int(data.get('difficulty', 1))
            )
            db.session.add(q)
            db.session.commit()
            return jsonify({'message': 'Đã thêm câu hỏi!', 'id': q.id}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

@app.route('/api/admin/survival-questions/<int:qid>', methods=['PUT', 'DELETE'])
def api_admin_survival_question_detail(qid):
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    q = SurvivalQuestion.query.get(qid)
    if not q:
        return jsonify({'error': 'Không tìm thấy câu hỏi!'}), 404
    
    if request.method == 'PUT':
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Dữ liệu không hợp lệ'}), 400
        try:
            q.question = data.get('question', q.question)
            q.options = json.dumps(data.get('options', json.loads(q.options)))
            q.correct_answer = int(data.get('correct_answer', q.correct_answer))
            q.floor_level = int(data.get('floor_level', q.floor_level))
            q.difficulty = int(data.get('difficulty', q.difficulty))
            db.session.commit()
            return jsonify({'message': 'Đã cập nhật câu hỏi!'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400
    
    if request.method == 'DELETE':
        try:
            db.session.delete(q)
            db.session.commit()
            return jsonify({'message': 'Đã xóa câu hỏi!'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 400

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/init-db')
def init_db():
    db.create_all()
    return "✅ Database created!"

with app.app_context():
    db.create_all()
    
# ============================================================
# RUN
# ============================================================

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
