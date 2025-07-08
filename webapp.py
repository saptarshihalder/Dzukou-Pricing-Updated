from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import json
import os
from pathlib import Path
from datetime import datetime
import threading
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# optimisation utils from existing modules
from price_optimizer import optimize_price, bayesian_optimize_price, simulate_profit, run_ab_test, clean_prices, round_price
from utils import canonical_key

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'changeme')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///pricing.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "product_data"
DATA_DIR.mkdir(exist_ok=True)

# database
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    keywords = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)

class ScrapingSite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    search_pattern = db.Column(db.String(200))
    requires_selenium = db.Column(db.Boolean, default=False)
    selector_config = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)

class ScrapingJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(50), default='pending')
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    error_log = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    total_products = db.Column(db.Integer, default=0)

class ScrapingResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('scraping_job.id'))
    site_id = db.Column(db.Integer, db.ForeignKey('scraping_site.id'))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    product_name = db.Column(db.String(500))
    price = db.Column(db.Float)
    currency = db.Column(db.String(10), default='EUR')
    url = db.Column(db.String(1000))
    scraped_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# --- scraper helper ---
class EnhancedProductScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0'})

    def get_chrome_options(self):
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        return options

    def clean_price(self, text):
        if not text:
            return None, None
        text = str(text)
        numbers = ''.join(c for c in text if c.isdigit() or c in ',.')
        if not numbers:
            return None, None
        return float(numbers.replace(',', '.')), 'EUR'

    def extract_with_config(self, soup, config):
        try:
            selectors = json.loads(config) if isinstance(config, str) else config
        except Exception:
            selectors = {}
        container_sel = selectors.get('container', 'div')
        name_sel = selectors.get('name', 'h1, h2, h3')
        price_sel = selectors.get('price', '.price')
        products = []
        for c in soup.select(container_sel)[:50]:
            name_elem = c.select_one(name_sel)
            price_elem = c.select_one(price_sel)
            name = name_elem.get_text(strip=True) if name_elem else None
            price_text = price_elem.get_text(strip=True) if price_elem else None
            price, currency = self.clean_price(price_text)
            if name and price:
                products.append({'name': name, 'price': price, 'currency': currency})
        return products

    def scrape_with_requests(self, site, url):
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, 'html.parser')
                return self.extract_with_config(soup, site.selector_config)
        except Exception:
            pass
        return []

    def scrape_with_selenium(self, site, url):
        driver = None
        try:
            driver = webdriver.Chrome(options=self.get_chrome_options())
            driver.get(url)
            time.sleep(3)
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            return self.extract_with_config(soup, site.selector_config)
        except Exception:
            return []
        finally:
            if driver:
                driver.quit()

    def scrape_site(self, site, terms):
        results = []
        for term in terms:
            url = site.url + site.search_pattern.format(term)
            if site.requires_selenium:
                products = self.scrape_with_selenium(site, url)
            else:
                products = self.scrape_with_requests(site, url)
            for p in products:
                p['search_term'] = term
                results.append(p)
            time.sleep(1)
        return results

scrape_status = {'active': False, 'progress': 0, 'message': ''}

# --- routes ---
@app.route('/')
@login_required
def index():
    return 'Pricing dashboard coming soon'

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('index'))
        flash('Invalid credentials')
    return '<form method="post">User: <input name="username">Pass: <input name="password" type="password"><input type="submit"></form>'

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/add_site', methods=['POST'])
@login_required
def add_site():
    data = request.json
    site = ScrapingSite(
        name=data['name'],
        url=data['url'].rstrip('/'),
        search_pattern=data.get('search_pattern', '/search?q={}'),
        requires_selenium=data.get('requires_selenium', False),
        selector_config=json.dumps(data.get('selector_config', {}))
    )
    db.session.add(site)
    db.session.commit()
    return jsonify({'success': True, 'id': site.id})

@app.route('/scrape', methods=['POST'])
@login_required
def start_scrape():
    if scrape_status['active']:
        return jsonify({'success': False, 'error': 'Scraper already running'}), 400
    data = request.json or {}
    category_ids = data.get('categories', [])
    site_ids = data.get('sites', [])

    def run():
        scrape_status.update({'active': True, 'progress': 0, 'message': 'Running'})
        job = ScrapingJob(status='running', started_at=datetime.utcnow(), created_by=current_user.id)
        db.session.add(job)
        db.session.commit()
        try:
            categories = Category.query.filter(Category.id.in_(category_ids)).all() if category_ids else Category.query.filter_by(active=True).all()
            sites = ScrapingSite.query.filter(ScrapingSite.id.in_(site_ids)).all() if site_ids else ScrapingSite.query.filter_by(active=True).all()
            total = len(categories) * len(sites)
            done = 0
            scraper = EnhancedProductScraper()
            total_products = 0
            for category in categories:
                terms = json.loads(category.keywords or '[]')
                if not terms:
                    continue
                for site in sites:
                    products = scraper.scrape_site(site, terms)
                    for p in products:
                        r = ScrapingResult(
                            job_id=job.id,
                            site_id=site.id,
                            category_id=category.id,
                            product_name=p['name'],
                            price=p['price'],
                            currency=p['currency'],
                            url=p.get('url')
                        )
                        db.session.add(r)
                    total_products += len(products)
                    done += 1
                    scrape_status['progress'] = int(done / total * 100)
                    db.session.commit()
            job.status='completed'
            job.total_products = total_products
            job.completed_at = datetime.utcnow()
        except Exception as e:
            job.status='failed'
            job.error_log=str(e)
        finally:
            scrape_status.update({'active': False, 'message': 'finished'})
            db.session.commit()
    threading.Thread(target=run, daemon=True).start()
    return jsonify({'success': True})

@app.route('/scrape_status')
@login_required
def get_status():
    return jsonify(scrape_status)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
