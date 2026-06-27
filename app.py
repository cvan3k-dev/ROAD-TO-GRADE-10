from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import UserMixin
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
    
    # ===== CHẾ ĐỘ NORMAL =====
    normal_mode_best = db.Column(db.Integer, default=0)       # Level cao nhất đạt được
    normal_checkpoint = db.Column(db.Integer, default=0)      # Checkpoint (level đã qua)
    normal_hp = db.Column(db.Integer, default=100)            # HP hiện tại
    normal_max_hp = db.Column(db.Integer, default=100)        # HP tối đa
    
    # ===== CHẾ ĐỘ SURVIVAL (VƯỢT TẦNG) =====
    survival_high_score = db.Column(db.Integer, default=0)    # Số tầng cao nhất đạt được
    survival_current_floor = db.Column(db.Integer, default=1) # Tầng hiện tại
    survival_hp = db.Column(db.Integer, default=100)          # HP hiện tại
    survival_max_hp = db.Column(db.Integer, default=100)      # HP tối đa
    survival_bosses_killed = db.Column(db.Integer, default=0) # Boss đã tiêu diệt trong run hiện tại

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
    
    # Tạo admin
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            level=10,
            xp=5000,
            coins=1000,
            rank='Huyền thoại'
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Đã tạo admin: admin / admin123")
    
    # Tạo thành tích
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
        2: [
            {'q': 'Chia động từ: She ___ to school every day.', 'options': ['go', 'goes', 'going', 'went'], 'a': 1},
            {'q': 'Chia động từ: They ___ football.', 'options': ['play', 'plays', 'playing', 'played'], 'a': 0},
            {'q': 'Từ "beautiful" có nghĩa là gì?', 'options': ['Xấu xí', 'Đẹp', 'Cao', 'Thấp'], 'a': 1},
            {'q': 'Phủ định: "He likes cats." → He ___ cats.', 'options': ["don't like", "doesn't like", "not like", "isn't like"], 'a': 1},
            {'q': 'Nghi vấn: "They play football" → ___ they play football?', 'options': ['Do', 'Does', 'Are', 'Is'], 'a': 0},
        ],
        3: [
            {'q': 'Sửa lỗi: "He don\'t like coffee."', 'options': ['He doesn\'t like coffee.', 'He don\'t likes coffee.', 'He not like coffee.', 'He doesn\'t likes coffee.'], 'a': 0},
            {'q': 'Từ "beautiful" là loại từ gì?', 'options': ['Tính từ', 'Danh từ', 'Động từ', 'Trạng từ'], 'a': 0},
            {'q': '"I am going to study" nghĩa là gì?', 'options': ['Tôi đang học', 'Tôi sẽ học', 'Tôi đã học', 'Tôi học'], 'a': 1},
            {'q': 'Quá khứ của "go" là gì?', 'options': ['goed', 'went', 'gone', 'going'], 'a': 1},
            {'q': 'Từ nào là tính từ?', 'options': ['Beautiful', 'Run', 'Table', 'Quickly'], 'a': 0},
        ],
        4: [
            {'q': 'Câu bị động của "She writes a letter" là gì?', 'options': ['A letter is written by her.', 'A letter was written by her.', 'A letter is being written by her.', 'A letter has been written by her.'], 'a': 0},
            {'q': 'He cleans the room. → The room ___ by him.', 'options': ['is cleaned', 'was cleaned', 'cleans', 'cleaned'], 'a': 0},
            {'q': 'They built this house in 2000. → This house ___ in 2000.', 'options': ['is built', 'was built', 'builds', 'built'], 'a': 1},
            {'q': '"Deadline" có nghĩa là gì?', 'options': ['Cuộc họp', 'Báo cáo', 'Hạn chót', 'Thư điện tử'], 'a': 2},
            {'q': '"Meeting" có nghĩa là gì?', 'options': ['Cuộc họp', 'Thuyết trình', 'Báo cáo', 'Hạn chót'], 'a': 0},
        ],
        5: [
            {'q': 'Từ nào là đại từ quan hệ?', 'options': ['Who', 'And', 'But', 'So'], 'a': 0},
            {'q': 'Chọn đại từ quan hệ: The man ___ is standing there is my brother.', 'options': ['who', 'which', 'whom', 'whose'], 'a': 0},
            {'q': 'If it rains, I ___ stay home.', 'options': ['will', 'would', 'am', 'was'], 'a': 0},
            {'q': 'If you study hard, you ___ pass the exam.', 'options': ['will', 'would', 'are', 'were'], 'a': 0},
            {'q': 'Câu điều kiện loại 1: If she ___ , I will tell her.', 'options': ['comes', 'came', 'come', 'coming'], 'a': 0},
        ],
        6: [
            {'q': 'Từ "Passive Voice" có nghĩa là gì?', 'options': ['Câu bị động', 'Câu chủ động', 'Câu điều kiện', 'Câu hỏi'], 'a': 0},
            {'q': 'Câu bị động của "He eats an apple" là gì?', 'options': ['An apple is eaten by him.', 'An apple was eaten by him.', 'An apple is being eaten by him.', 'An apple has been eaten by him.'], 'a': 0},
            {'q': 'She wrote a letter. → A letter ___ by her.', 'options': ['is written', 'was written', 'is being written', 'has been written'], 'a': 1},
            {'q': 'They will build a house. → A house ___ by them.', 'options': ['is built', 'was built', 'will be built', 'has been built'], 'a': 2},
            {'q': 'Từ nào là động từ bất quy tắc?', 'options': ['go', 'play', 'walk', 'talk'], 'a': 0},
        ],
        7: [
            {'q': 'Relative Clause là gì?', 'options': ['Mệnh đề quan hệ', 'Mệnh đề điều kiện', 'Mệnh đề thời gian', 'Mệnh đề nguyên nhân'], 'a': 0},
            {'q': 'The book ___ is on the table is mine.', 'options': ['who', 'which', 'whom', 'whose'], 'a': 1},
            {'q': 'The girl ___ I met is a doctor.', 'options': ['who', 'which', 'whom', 'whose'], 'a': 2},
            {'q': 'Từ "that" có thể thay thế cho từ nào?', 'options': ['who', 'which', 'whom', 'Tất cả'], 'a': 3},
            {'q': 'Mệnh đề quan hệ dùng để làm gì?', 'options': ['Bổ nghĩa cho danh từ', 'Bổ nghĩa cho động từ', 'Bổ nghĩa cho tính từ', 'Bổ nghĩa cho trạng từ'], 'a': 0},
        ],
        8: [
            {'q': 'Dịch nhanh: "Tôi đang học bài."', 'options': ['I am studying.', 'I study.', 'I studied.', 'I will study.'], 'a': 0},
            {'q': 'Dịch nhanh: "Họ đã đi đến trường."', 'options': ['They go to school.', 'They went to school.', 'They are going to school.', 'They will go to school.'], 'a': 1},
            {'q': 'Từ nào có nghĩa là "nhanh chóng"?', 'options': ['Quickly', 'Slowly', 'Carefully', 'Loudly'], 'a': 0},
            {'q': 'Dịch nhanh: "Cô ấy sẽ đến vào ngày mai."', 'options': ['She comes tomorrow.', 'She came tomorrow.', 'She will come tomorrow.', 'She is coming tomorrow.'], 'a': 2},
            {'q': 'Từ nào trái nghĩa với "fast"?', 'options': ['Slow', 'Quick', 'Rapid', 'Swift'], 'a': 0},
        ],
        9: [
            {'q': 'Từ nào là từ vựng về trường học?', 'options': ['Teacher', 'Forest', 'Mountain', 'Ocean'], 'a': 0},
            {'q': 'Từ "survival" có nghĩa là gì?', 'options': ['Sinh tồn', 'Chiến thắng', 'Thất bại', 'Hòa bình'], 'a': 0},
            {'q': 'Từ nào là động từ?', 'options': ['Run', 'Happy', 'Beautiful', 'Quickly'], 'a': 0},
            {'q': '"Mode" có nghĩa là gì?', 'options': ['Chế độ', 'Mô hình', 'Phương thức', 'Cách thức'], 'a': 0},
            {'q': 'Từ "survive" có nghĩa là gì?', 'options': ['Sống sót', 'Chết', 'Chiến thắng', 'Thất bại'], 'a': 0},
        ],
        10: [
            {'q': 'Dịch: "Tôi sẽ vượt qua kỳ thi."', 'options': ['I will pass the exam.', 'I pass the exam.', 'I passed the exam.', 'I am passing the exam.'], 'a': 0},
            {'q': '"Castle" có nghĩa là gì?', 'options': ['Lâu đài', 'Cung điện', 'Ngôi nhà', 'Tháp'], 'a': 0},
            {'q': 'Từ "exam" có nghĩa là gì?', 'options': ['Kỳ thi', 'Bài học', 'Bài tập', 'Điểm số'], 'a': 0},
            {'q': 'Dịch: "Chúng tôi đã học rất chăm chỉ."', 'options': ['We studied very hard.', 'We study very hard.', 'We are studying very hard.', 'We will study very hard.'], 'a': 0},
            {'q': '"Lord" có nghĩa là gì?', 'options': ['Chúa tể', 'Vua', 'Quý tộc', 'Lãnh chúa'], 'a': 0},
        ],
    }
    return questions_pool.get(level_id, questions_pool[1])

# ============================================================
# ROUTES
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

# ===== CHẾ ĐỘ NORMAL =====
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

# ===== CHẾ ĐỘ SURVIVAL (VƯỢT TẦNG) =====
@app.route('/game/survival')
def survival_game():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    # Lấy câu hỏi từ level ngẫu nhiên (1-10)
    import random
    level_id = random.randint(1, 10)
    questions = get_questions(level_id)
    selected = random.sample(questions, min(3, len(questions)))
    return render_template('game.html', user=user, level={'id': level_id, 'name': 'Survival', 'boss': 'Survival Boss'}, questions=selected, mode='survival')

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

@app.route('/api/survival/floor', methods=['POST'])
def survival_floor():
    """Khi vượt qua một tầng (Survival Mode)"""
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

@app.route('/api/survival/reset', methods=['POST'])
def survival_reset():
    """Reset Survival Mode (khi chết)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Chưa đăng nhập!'}), 401
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User không tồn tại!'}), 404
    
    # Lưu high score nếu cao hơn
    if user.survival_bosses_killed > user.survival_high_score:
        user.survival_high_score = user.survival_bosses_killed
    user.survival_current_floor = 1
    user.survival_bosses_killed = 0
    user.survival_hp = user.survival_max_hp
    db.session.commit()
    
    return jsonify({
        'success': True,
        'high_score': user.survival_high_score
    })

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
# ADMIN
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
    level_counts = {}
    for i in range(1, 11):
        level_counts[i] = User.query.filter_by(level=i).count()
    total_users = len(users)
    total_xp = sum(u.xp for u in users)
    avg_level = round(sum(u.level for u in users) / total_users, 1) if total_users > 0 else 0
    return render_template('admin_dashboard.html', 
        users=users, total_users=total_users, total_xp=total_xp,
        avg_level=avg_level, level_counts=level_counts
    )

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# ============================================================
# RUN
# ============================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
