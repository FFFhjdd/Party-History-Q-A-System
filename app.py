from flask import Flask, request, render_template, redirect, url_for, flash
from py2neo import Graph
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
import pandas as pd
import math
import subprocess
import time
import os

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


# User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 启动 Neo4j 服务
def start_neo4j():
    try:
        neo4j_path = os.getenv('NEO4J_PATH', r"E:\neo4j-community-3.5.32\bin\neo4j.bat")
        subprocess.Popen([neo4j_path, "console"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(10)  # 等待几秒钟以确保 Neo4j 服务启动
    except Exception as e:
        print(f"Error starting Neo4j: {e}")

start_neo4j()

# 连接到Neo4j数据库
g = Graph("bolt://localhost:7687", auth=("neo4j", "123456"))

def get_entity_dictionary():
    query = """
    MATCH (n)
    RETURN DISTINCT labels(n)[0] AS Label, n.name AS Name
    """
    results = g.run(query).to_data_frame()
    entity_dict = pd.Series(results.Label.values, index=results.Name).to_dict()
    return entity_dict

def get_relationship_dictionary():
    rel_query = """
    CALL db.relationshipTypes() YIELD relationshipType
    RETURN relationshipType
    """
    rel_results = g.run(rel_query).to_data_frame()
    rel_dict = pd.Series(['关系'] * len(rel_results.relationshipType), index=rel_results.relationshipType).to_dict()
    return rel_dict

def get_property_dictionary():
    prop_query = """
    CALL db.labels() YIELD label
    RETURN label
    """
    prop_results = g.run(prop_query).to_data_frame()
    prop_dict = pd.Series(['属性'] * len(prop_results.label), index=prop_results.label).to_dict()
    return prop_dict

entity_dict = get_entity_dictionary()
rel_dict = get_relationship_dictionary()
prop_dict = get_property_dictionary()

rules = [
    "事件的关系？",
    "会议的关系？",
    "文件的关系？",
    "人物关系的属性？",
    "文件关系的属性？",
    "组织关系的属性？",
    "事件关系的属性？",
    "会议关系的属性？",
    "人物关系的属性的属性内容？",
    "属性时间人物关系的属性？",
    "属性时间人物关系的属性的属性内容？",
]

cypher_strs = [
    "MATCH (e1:事件 {name:'<名称>'})-[r:<关系>]->(e2) RETURN e2.name",
    "MATCH (m:会议 {name:'<名称>'})-[r:<关系>]->(n) RETURN n.name",
    "MATCH (f:文件 {name:'<名称>'})-[r:<关系>]->(n) RETURN n.name",
    "MATCH (p:人物 {name:'<名称>'})-[r:<关系>]->(t) RETURN t.name",
    "MATCH (f:文件 {name:'<名称>'})-[r:<关系>]->(n) RETURN n.name",
    "MATCH (o:组织 {name:'<名称>'})-[r:<关系>]->(e) RETURN e.name",
    "MATCH (e1:事件 {name:'<名称>'})-[r:<关系>]->(e2) RETURN e2.name",
    "MATCH (m:会议 {name:'<名称>'})-[r:<关系>]->(e) RETURN e.name",
    "MATCH (p:人物 {name:'<名称>'})-[:<关系>]->(f:<属性>)-[:包含]->(t:文件内容) RETURN t.name",
    "MATCH (p:人物 {name: '<名称>'})-[:<关系>]->(f:<属性>)-[:发布时间]->(ft:文件时间) WHERE ft.name = '<时间>' RETURN f.name",
    "MATCH (p:人物 {name: '<名称>'})-[:<关系>]->(f:<属性>)-[:包含]->(t:文件内容) WHERE (f)-[:发布时间]->(:文件时间 {name: '<时间>'}) RETURN t.name",
]

def get_kwords(obj_dict, q):
    max_len = 12
    word_list = []
    start = 0
    while start < len(q):
        end_cut_pos = min(start + max_len, len(q))
        current_s = q[start:end_cut_pos]
        is_cut_words = False
        for i in range(end_cut_pos - start):
            current_s = q[start:end_cut_pos]
            if current_s in list(obj_dict.keys()):
                word_list.append((current_s, start, end_cut_pos, obj_dict[current_s]))
                start = end_cut_pos
                is_cut_words = True
                break
            else:
                end_cut_pos -= 1
        if not is_cut_words:
            start += 1
    return word_list

def generate_template(obj_list, q):
    template_q = q
    for obj in obj_list:
        template_q = template_q.replace(obj[0], f"{obj[3]}")
    return template_q

def match_template_and_generate_cypher(template_q, rules, cypher_strs, obj_list):
    if template_q in rules:
        index = rules.index(template_q)
        cypher_template = cypher_strs[index]
        for obj in obj_list:
            if obj[3] == "属性":
                cypher_template = cypher_template.replace("<属性>", obj[0])
            elif obj[3] == "关系":
                cypher_template = cypher_template.replace("<关系>", obj[0])
            elif obj[3] in ["人物", "事件", "会议", "思想", "文件", "组织"]:
                cypher_template = cypher_template.replace("<名称>", obj[0])
            elif obj[3] in ["文件时间"]:
                cypher_template = cypher_template.replace("<时间>", obj[0])
        return cypher_template
    return None

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, email=email, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('您的账号已创建，请登录！', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user, remember=request.form.get('remember'))
            return redirect(url_for('index'))
        else:
            flash('登录失败，请检查您的用户名和密码', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    query = request.form.get('query') if request.method == 'POST' else request.args.get('query', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    results = []
    total_results = 0

    if query:
        entity_list = get_kwords(entity_dict, query)
        rel_list = get_kwords(rel_dict, query)
        prop_list = get_kwords(prop_dict, query)
        obj_list = entity_list + rel_list + prop_list
        obj_list = sorted(obj_list, key=lambda x: x[1])
        template_q = generate_template(obj_list, query)
        final_cypher = match_template_and_generate_cypher(template_q, rules, cypher_strs, obj_list)
        if final_cypher:
            all_results = g.run(final_cypher).data()
            total_results = len(all_results)
            start = (page - 1) * per_page
            end = start + per_page
            results = all_results[start:end]
            values_list = [list(item.values())[0] for item in results]
            total_pages = math.ceil(total_results / per_page)
            return render_template('index.html', query=query, result=values_list, page=page, total_pages=total_pages)

    return render_template('index.html', query=query, result=results, page=page, total_pages=1)

@app.route('/search', methods=['GET'])
@login_required
def search():
    keyword = request.args.get('keyword', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    results = []
    total_results = 0

    if keyword:
        query = f"""
        MATCH (n)
        WHERE n.name CONTAINS '{keyword}'
        RETURN n.name AS name, labels(n)[0] AS label
        """
        all_results = g.run(query).data()
        total_results = len(all_results)
        start = (page - 1) * per_page
        end = start + per_page
        results = all_results[start:end]

    total_pages = math.ceil(total_results / per_page)
    return render_template('search.html', keyword=keyword, results=results, page=page, total_pages=total_pages)

if __name__ == '__main__':
    app.run(debug=True)
