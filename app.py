from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
from datetime import datetime, timedelta
import random

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Cấu hình database (SQLite)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'road_to_grade10.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
CORS(app)

# ============================================================
# MODELS
# ============================================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    level = db.Column(db.Integer, default=1)
    xp = db.Column(db.Integer, default=0)
    coins = db.Column(db.Integer, default=0)
    streak = db.Column(db.Integer, default=0)
    rank = db.Column(db.String(50), default='Chiến binh')
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    achievements = db.Column(db.Text, default='[]')  # Lưu JSON
    # Thống kê học tập
    total_lessons = db.Column(db.Integer, default=0)
    total_correct = db.Column(db.Integer, default=0)
    total_wrong = db.Column(db.Integer, default=0)
    accuracy = db.Column(db.Float, default=0.0)

class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    condition = db.Column(db.String(100))

class UserAchievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    achievement_id = db.Column(db.Integer, db.ForeignKey('achievement.id'), nullable=False)
    unlocked_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============================================================
# TẠO BẢNG VÀ DỮ LIỆU MẪU
# ============================================================

with app.app_context():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db.create_all()
    
    # Tạo admin nếu chưa có
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            level=10,
            xp=5000,
            coins=1000,
            rank='Huyền thoại',
            is_admin=True,
            total_lessons=50,
            total_correct=45,
            total_wrong=5,
            accuracy=90.0
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Đã tạo admin: admin / admin123")
    
    # Tạo thành tích mẫu
    if Achievement.query.count() == 0:
        achievements = [
            {'name': 'Người mới', 'description': 'Hoàn thành Level 1', 'icon': '🌱', 'condition': 'level >= 1'},
            {'name': 'Chiến binh', 'description': 'Đạt Level 5', 'icon': '⚔️', 'condition': 'level >= 5'},
            {'name': 'Hiệp sĩ', 'description': 'Đạt Level 10', 'icon': '🛡️', 'condition': 'level >= 10'},
            {'name': 'Nhà thám hiểm', 'description': 'Hoàn thành 5 Level', 'icon': '🗺️', 'condition': 'level >= 5'},
            {'name': 'Huyền thoại', 'description': 'Đạt Level 10', 'icon': '🏆', 'condition': 'level >= 10'},
        ]
        for a in achievements:
            db.session.add(Achievement(**a))
        db.session.commit()
        print("✅ Đã tạo thành tích mẫu")

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
    all_achievements = Achievement.query.all()
    
    new_achievements = []
    for ach in all_achievements:
        ach_id = f'ach_{ach.id}'
        if ach_id in current: continue
        
        if ach.condition.startswith('level >= '):
            req_level = int(ach.condition.split('>=')[1].strip())
            if user.level >= req_level:
                new_achievements.append(ach_id)
                ua = UserAchievement(user_id=user.id, achievement_id=ach.id)
                db.session.add(ua)
    
    if new_achievements:
        user.achievements = json.dumps(list(set(current + new_achievements)))
        db.session.commit()

# ============================================================
# ROUTES (GIỮ NGUYÊN CODE CŨ)
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
    # Lấy top 5 leaderboard
    leaderboard = User.query.order_by(User.xp.desc()).limit(5).all()
    all_ach = Achievement.query.all()
    unlocked = json.loads(user.achievements) if user.achievements else []
    return render_template('index.html', user=user, leaderboard=leaderboard, all_ach=all_ach, unlocked=unlocked)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            user.last_login = datetime.utcnow()
            db.session.commit()
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
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

@app.route('/leaderboard')
def leaderboard():
    users = User.query.order_by(User.xp.desc()).limit(20).all()
    return render_template('leaderboard.html', users=users)

@app.route('/game/<int:level_id>')
def game(level_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    levels = get_levels()
    level = next((l for l in levels if l['id'] == level_id), None)
    if not level:
        return "Level không tồn tại!", 404
    
    questions = {
        1: {'question': 'Từ nào có nghĩa là "mèo"?', 'options': ['Dog', 'Cat', 'Bird', 'Fish'], 'answer': 1},
        2: {'question': 'Chia động từ: She ___ to school every day.', 'options': ['go', 'goes', 'going', 'went'], 'answer': 1},
        3: {'question': 'Từ "beautiful" có nghĩa là gì?', 'options': ['Xấu xí', 'Đẹp', 'Cao', 'Thấp'], 'answer': 1},
        4: {'question': 'Sửa lỗi: "He don\'t like coffee."', 'options': ['He doesn\'t like coffee.', 'He don\'t likes coffee.', 'He not like coffee.', 'He doesn\'t likes coffee.'], 'answer': 0},
        5: {'question': 'Từ nào là từ vựng về động vật?', 'options': ['Elephant', 'Table', 'Happy', 'Run'], 'answer': 0},
        6: {'question': 'Câu bị động của "She writes a letter" là gì?', 'options': ['A letter is written by her.', 'A letter was written by her.', 'A letter is being written by her.', 'A letter has been written by her.'], 'answer': 0},
        7: {'question': 'Chọn đại từ quan hệ: The man ___ is standing there is my brother.', 'options': ['who', 'which', 'whom', 'whose'], 'answer': 0},
        8: {'question': 'Dịch nhanh: "Tôi đang học bài."', 'options': ['I am studying.', 'I study.', 'I studied.', 'I will study.'], 'answer': 0},
        9: {'question': 'Từ nào là từ vựng về trường học?', 'options': ['Teacher', 'Forest', 'Mountain', 'Ocean'], 'answer': 0},
        10: {'question': 'Dịch: "Tôi sẽ vượt qua kỳ thi."', 'options': ['I will pass the exam.', 'I pass the exam.', 'I passed the exam.', 'I am passing the exam.'], 'answer': 0},
    }
    
    q = questions.get(level_id, questions[1])
    return render_template('game.html', user=user, level=level, question=q)

@app.route('/api/attack', methods=['POST'])
def attack():
    if 'user_id' not in session:
        return jsonify({'error': 'Chưa đăng nhập!'}), 401
    
    data = request.json
    level_id = data.get('level_id')
    answer = data.get('answer')
    
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'Không tìm thấy user!'}), 404
    
    questions = {
        1: {'answer': 1},
        2: {'answer': 1},
        3: {'answer': 1},
        4: {'answer': 0},
        5: {'answer': 0},
        6: {'answer': 0},
        7: {'answer': 0},
        8: {'answer': 0},
        9: {'answer': 0},
        10: {'answer': 0},
    }
    
    correct = questions.get(level_id, {}).get('answer', 0)
    is_correct = (answer == correct)
    
    # Cập nhật thống kê
    user.total_lessons += 1
    if is_correct:
        user.total_correct += 1
    else:
        user.total_wrong += 1
    user.accuracy = round((user.total_correct / user.total_lessons) * 100, 1)
    
    if is_correct:
        xp_gain = 50 + level_id * 10
        user.xp += xp_gain
        new_level = min(10, user.xp // 200 + 1)
        if new_level > user.level:
            user.level = new_level
            user.rank = calculate_rank(new_level)
        user.coins += 10
        db.session.commit()
        check_achievements(user.id)
        return jsonify({
            'correct': True,
            'message': f'⚔️ Chính xác! +{xp_gain} XP, +10 Coin!',
            'xp': user.xp,
            'level': user.level,
            'coins': user.coins,
            'accuracy': user.accuracy
        })
    else:
        db.session.commit()
        return jsonify({
            'correct': False,
            'message': '❌ Sai rồi! Hãy thử lại!'
        })

# ============================================================
# ROUTES ADMIN (THÊM MỚI)
# ============================================================

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        return "Bạn không có quyền truy cập!", 403
    
    # Thống kê tổng quan
    total_users = User.query.count()
    total_lessons = db.session.query(db.func.sum(User.total_lessons)).scalar() or 0
    total_correct = db.session.query(db.func.sum(User.total_correct)).scalar() or 0
    total_wrong = db.session.query(db.func.sum(User.total_wrong)).scalar() or 0
    avg_accuracy = db.session.query(db.func.avg(User.accuracy)).scalar() or 0
    
    # Danh sách user
    users = User.query.order_by(User.xp.desc()).all()
    
    return render_template('admin.html',
        user=user,
        total_users=total_users,
        total_lessons=total_lessons,
        total_correct=total_correct,
        total_wrong=total_wrong,
        avg_accuracy=round(avg_accuracy, 1),
        users=users
    )

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password) and user.is_admin:
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            return redirect(url_for('admin_dashboard'))
        return render_template('admin_login.html', error='Sai tên đăng nhập hoặc mật khẩu!')
    return render_template('admin_login.html')

@app.route('/api/admin/users')
def admin_users():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'level': u.level,
        'xp': u.xp,
        'coins': u.coins,
        'rank': u.rank,
        'total_lessons': u.total_lessons,
        'total_correct': u.total_correct,
        'total_wrong': u.total_wrong,
        'accuracy': u.accuracy,
        'created_at': u.created_at.strftime('%d/%m/%Y')
    } for u in users])

@app.route('/api/admin/stats')
def admin_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    user = User.query.get(session['user_id'])
    if not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    total_users = User.query.count()
    total_lessons = db.session.query(db.func.sum(User.total_lessons)).scalar() or 0
    total_correct = db.session.query(db.func.sum(User.total_correct)).scalar() or 0
    avg_accuracy = db.session.query(db.func.avg(User.accuracy)).scalar() or 0
    
    return jsonify({
        'total_users': total_users,
        'total_lessons': total_lessons,
        'total_correct': total_correct,
        'avg_accuracy': round(avg_accuracy, 1)
    })

# ============================================================
# RUN
# ============================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
