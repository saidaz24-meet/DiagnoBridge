import os
from flask import Flask, flash, jsonify, render_template, request, redirect, url_for, session, send_from_directory
from flask_socketio import SocketIO, join_room, leave_room, send
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore, auth, messaging
from dotenv import load_dotenv
import json
# import pushy


# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'super-secret-key'
socketio = SocketIO(app)

# Load Firebase credentials from environment variable
firebase_creds = json.loads(os.getenv('FIREBASE_SERVICE_ACCOUNT'))

# Initialize Firebase Admin SDK
cred = credentials.Certificate(firebase_creds)
firebase_admin.initialize_app(cred)

# Initialize Firestore
db = firestore.client()


# Read VAPID keys from environment variables
VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY')
VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY')
VAPID_CLAIMS = {"sub": "mailto:your-email@example.com"}

@app.route('/static/js/firebase-messaging-sw.js')
def service_worker():
    return app.send_static_file('js/firebase-messaging-sw.js')


@app.route('/register_device', methods=['POST'])
def register_device():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    token = request.json.get('token')
    if not token:
        return jsonify({'error': 'No token provided'}), 400

    user_ref = db.collection('users').document(user_id)
    user_ref.update({'fcm_token': token})
    return jsonify({'success': True}), 200

def send_fcm_notification(token, title, body):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        token=token,
        webpush=messaging.WebpushConfig(
            vapid_key=VAPID_PUBLIC_KEY,
            headers={
                'Authorization': f'Bearer {VAPID_PRIVATE_KEY}'
            }
        )
    )
    response = messaging.send(message)
    print('Successfully sent message:', response)


@app.route('/', methods=['GET', 'POST'])
def index():
    error = ""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user_name = request.form['user_name']
        phone = request.form['phone']

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
                "password": password,
                "user_name": user_name,
                "phone": phone,
                "role": "user",

            }
            db.collection('users').document(UID).set(user_data)

            # Create chat room with manager
            manager_ref = db.collection('users').where('role', '==', 'manager').limit(1).stream()
            manager_id = list(manager_ref)[0].id if manager_ref else None
            if manager_id:
                chat_room_data = {
                    'user1': manager_id,
                    'user2': UID,
                }
                chat_room_ref = db.collection('chatRooms').document()
                chat_room_ref.set(chat_room_data)

                # Initialize an empty message in the messages subcollection
                chat_room_ref.collection('messages').add({
                    'sender': 'system',
                    'content': 'Chat started',
                    'timestamp': datetime.now(timezone.utc)
                })

            # Set login session
            session['user_id'] = UID
            session['user_name'] = user_name

            return redirect(url_for('chat_room', chat_id=chat_room_ref.id))

        except Exception as e:
            error = str(e)
            print(f"Authentication failed: {error}")

    return render_template("signup.html", error=error)

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
            if user['password'] == password:  # Ensure to hash and check hashed passwords in production

                # Set session variables
                session['user_id'] = users[0].id  # Store Firestore document ID as user_id
                session['email'] = user['email']
                session['user_name'] = user['user_name']

                flash('Login successful!', 'success')

                if user['role'] == 'manager':
                    return redirect(url_for('homepage'))
                else:
                    chat_room_ref = db.collection('chatRooms').where('user2', '==', users[0].id).limit(1).stream()
                    chat_room_id = list(chat_room_ref)[0].id if chat_room_ref else None
                    return redirect(url_for('chat_room', chat_id=chat_room_id))
            else:
                flash('Incorrect password. Please try again.', 'error')
        else:
            flash('User does not exist.', 'error')

    return render_template('signin.html')

@app.route('/homepage')
def homepage():
    user_id = session.get('user_id')
    user_name = session.get('user_name')

    if not user_id:
        return redirect(url_for('signin'))

    user_doc = db.collection('users').document(user_id).get()

    if user_doc.exists:
        user_data = user_doc.to_dict()
        role = user_data.get('role')

        if role == 'manager':
            chats = db.collection('chatRooms').stream()
            all_chats = []

            for chat in chats:
                chat_data = chat.to_dict()
                chat_id = chat.id
                user2_id = chat_data.get('user2')

                # Fetch the user2's data
                user2_doc = db.collection('users').document(user2_id).get()
                if user2_doc.exists:
                    user2_data = user2_doc.to_dict()
                    chat_data['user2_name'] = user2_data.get('user_name')
                else:
                    chat_data['user2_name'] = "Unknown"

                # Fetch the last message
                last_message_ref = chat.reference.collection('messages').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(1)
                last_message = [msg.to_dict() for msg in last_message_ref.stream()]
                chat_data['last_message'] = last_message[0] if last_message else None
                chat_data['chat_id'] = chat_id

                all_chats.append(chat_data)

            return render_template('homepage.html', chats=all_chats, user_id=user_id, user_name=user_name)
        else:
            return redirect(url_for('signin'))

    return redirect(url_for('signin'))

# Route for the chat room
@app.route('/chat/<chat_id>', methods=['GET', 'POST'])
def chat_room(chat_id):
    user_id = session.get('user_id')
    user_name = session.get('user_name')

    if not user_id:
        return redirect(url_for('signin'))

    user_doc = db.collection('users').document(user_id).get()
    if user_doc:
        user_data = user_doc.to_dict()
        user_role = user_data.get('role')
    else:
        return redirect(url_for('signin'))

    chat_ref = db.collection('chatRooms').document(chat_id)
    chat = chat_ref.get()

    if chat:
        chat_data = chat.to_dict()
        messages_ref = chat_ref.collection('messages').order_by('timestamp')
        messages = [msg.to_dict() for msg in messages_ref.stream()]

        # Convert Firestore timestamps to ISO format strings
        for message in messages:
            if isinstance(message['timestamp'], datetime):
                message['timestamp'] = message['timestamp'].isoformat()

        if request.method == 'POST':
            message_content = request.form['message']
            new_message = {
                'sender': user_name,
                'content': message_content,
                'timestamp': datetime.now(timezone.utc)  # Store as datetime object
            }
            chat_ref.collection('messages').add(new_message)
            chat_ref.update({'lastMessage': new_message})

            # Convert timestamp to ISO format for the emitted event
            new_message['timestamp'] = new_message['timestamp'].isoformat()

            # Emit new message event
            socketio.emit('new_message', new_message, room=chat_id)

            return jsonify(new_message)

        return render_template('chatRoom.html', chat=chat_data, messages=messages, user_name=user_name, user_id=user_id, user_role=user_role, chat_id=chat_id)

    return redirect(url_for('homepage'))

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    user_id = session.get('user_id')
    if user_id:
        # Clear session
        session.clear()

        # Update Firestore with offline status
        db.collection('users').document(user_id).update({'online': False})

    return redirect(url_for('signin'))

@app.route('/update_online_status', methods=['POST'])
def update_online_status():
    data = request.json
    user_id = data.get('user_id')
    online = data.get('online')

    if user_id:
        user_ref = db.collection('users').document(user_id)
        user_ref.update({'online': online})

        return jsonify({'success': True}), 200
    else:
        return jsonify({'error': 'User ID not provided.'}), 400

@app.route('/send_push_notification', methods=['POST'])
def send_push_notification():
    data = request.get_json()
    chat_id = data.get('chat_id')
    message_content = data.get('message')

    if not chat_id or not message_content:
        return jsonify({'error': 'chat_id and message are required'}), 400

    chat_ref = db.collection('chatRooms').document(chat_id)
    chat_data = chat_ref.get().to_dict()
    if not chat_data:
        return jsonify({'error': 'Chat not found'}), 404

    recipient_id = chat_data['user2'] if chat_data['user1'] == session.get('user_id') else chat_data['user1']
    
    recipient_ref = db.collection('users').document(recipient_id).get()
    if recipient_ref.exists:
        recipient_data = recipient_ref.to_dict()
        fcm_token = recipient_data.get('fcm_token')
        
        if fcm_token:
            send_fcm_notification(fcm_token, "New Message", message_content)
            return jsonify({'success': True}), 200
        else:
            return jsonify({'error': 'FCM token not found for the recipient'}), 400
    else:
        return jsonify({'error': 'Recipient not found'}), 404


# SocketIO events
@socketio.on('join')
def on_join(data):
    user_id = session.get('user_id')
    user_name = session.get('user_name')
    join_room(data['chat_id'])
    # Update Firestore with online status
    db.collection('users').document(user_id).update({'online': True})
    send(f'{user_name} has joined the room.', to=data['chat_id'])

@socketio.on('leave')
def on_leave(data):
    user_id = session.get('user_id')
    user_name = session.get('user_name')
    leave_room(data['chat_id'])
    # Update Firestore with offline status
    db.collection('users').document(user_id).update({'online': False})
    send(f'{user_name} has left the room.', to=data['chat_id'])

@socketio.on('new_message')
def handle_new_message(data):
    room = data['room']
    message_content = data['content']
    user_id = session.get('user_id')

    chat_ref = db.collection('chatRooms').document(room)
    new_message = {
        'sender': user_id,
        'content': message_content,
        'timestamp': datetime.now(timezone.utc)
    }
    chat_ref.collection('messages').add(new_message)
    socketio.emit('new_message', new_message, room=room)

    # Get the recipient user ID
    chat_data = chat_ref.get().to_dict()
    recipient_id = chat_data['user2'] if chat_data['user1'] == user_id else chat_data['user1']

    # Get the recipient user's FCM token
    recipient_ref = db.collection('users').document(recipient_id).get()
    if recipient_ref.exists:
        recipient_data = recipient_ref.to_dict()
        fcm_token = recipient_data.get('fcm_token')

        if fcm_token:
            send_fcm_notification(fcm_token, "New Message", message_content)
        else:
            print("FCM token not found for the recipient.")
    else:
        print("Recipient not found.")


if __name__ == '__main__':
    socketio.run(app, debug=True)
