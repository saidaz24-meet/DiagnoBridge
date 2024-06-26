from flask import Flask, flash, render_template, request, redirect, url_for, session as login_session
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore, auth

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'super-secret-key'

# Initialize Firebase Admin SDK
cred = credentials.Certificate('firebase_service_account.json')
firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()


# Route for signup
@app.route('/', methods=['GET', 'POST'])
def index():
    error = ""
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user_name = request.form['user_name']

        try:
            # Create user in Firebase Authentication
            user = auth.create_user(
                email=email,
                password=password
            )
            UID = user.uid
            
            # Store user data in Firestore
            user_data = {
                "email": email,
                "user_name": user_name,
                "password": password,
                "role": "user"
            }
            db.collection('users').document(UID).set(user_data)

            # Set login session
            login_session['user_id'] = UID

            return redirect(url_for('homepage'))

        except Exception as e:
            error = str(e)
            print(f"Authentication failed: {error}")

    return render_template("signup.html", error=error)

# Route for signin
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Query Firestore to check if user exists and credentials are correct
        user_ref = db.collection('users').where('email', '==', email).limit(1)
        users = list(user_ref.stream())

        if len(users) == 1:
            user = users[0].to_dict()
            if user['password'] == password:
                # Set session variables
                login_session['user_id'] = users[0].id  # Store Firestore document ID as user_id
                login_session['email'] = user['email']
                login_session['username'] = user['user_name']

                flash('Login successful!', 'success')
                return redirect(url_for('homepage'))
            else:
                flash('Incorrect password. Please try again.', 'error')
        else:
            flash('User does not exist.', 'error')

    return render_template('signin.html')


# Route for homepage
@app.route('/homepage')
def homepage():
    user_id = login_session.get('user_id')

    if not user_id:
        return redirect(url_for('signin'))

    user_doc = db.collection('users').document(user_id).get()

    if user_doc.exists:
        user_data = user_doc.to_dict()
        role = user_data.get('role')

        if role == 'manager':
            chats = db.collection('chats').stream()
            all_chats = [chat.to_dict() for chat in chats]
            return render_template('homepage.html', chats=all_chats)
        else:
            chats = db.collection('chats').where('user2', '==', user_id).stream()
            user_chats = [chat.to_dict() for chat in chats]
            return render_template('homepage.html', chats=user_chats)

    return redirect(url_for('signin'))

# Route for chat room
@app.route('/chat/<chat_id>', methods=['GET', 'POST'])
def chat_room(chat_id):
    user_id = login_session.get('user_id')

    if not user_id:
        return redirect(url_for('signin'))

    chat_ref = db.collection('chats').document(chat_id)
    chat = chat_ref.get()

    if chat.exists:
        chat_data = chat.to_dict()

        if user_id == chat_data['user1'] or user_id == chat_data['user2']:
            messages_ref = chat_ref.collection('messages').order_by('timestamp')
            messages = [msg.to_dict() for msg in messages_ref.stream()]

            if request.method == 'POST':
                message_content = request.form['message']
                new_message = {
                    'sender': user_id,
                    'content': message_content,
                    'timestamp': datetime.utcnow()
                }
                chat_ref.collection('messages').add(new_message)
                chat_ref.update({'lastMessage': new_message})

            return render_template('chatRoom.html', chat=chat_data, messages=messages)

    return redirect(url_for('homepage'))

if __name__ == '__main__':
    app.run(debug=True)
