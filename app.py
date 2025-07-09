from flask import Flask, render_template, request, jsonify, send_file
import subprocess
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/manage-products', methods=['GET', 'POST'])
def manage_products():
    if request.method == 'POST':
        try:
            result = subprocess.run(['python', 'manage_products.py'],
                                    capture_output=True, text=True)
            return jsonify({'status': 'success', 'output': result.stdout})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)})
    return render_template('manage_products.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    try:
        result = subprocess.run(['python', 'scraper.py'],
                                capture_output=True, text=True)
        return jsonify({'status': 'success', 'output': result.stdout})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/optimize', methods=['POST'])
def optimize():
    try:
        result = subprocess.run(['python', 'price_optimizer.py'],
                                capture_output=True, text=True)
        return jsonify({'status': 'success', 'output': result.stdout})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/dashboard')
def dashboard():
    try:
        subprocess.run(['python', 'dashboard.py'])
        return send_file('dashboard.html')
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
