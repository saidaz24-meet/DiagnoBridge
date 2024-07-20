// Import Firebase scripts from local paths
import { initializeApp } from '/static/js/firebase-app.js';
import { getMessaging, getToken, onMessage } from '/static/js/firebase-messaging.js';

// Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyC8xq78KFmMbCJrK-3ko6djACxMBwUDPmY",
  authDomain: "messaging-web-9d1e9.firebaseapp.com",
  databaseURL: "https://messaging-web-9d1e9-default-rtdb.firebaseio.com",
  projectId: "messaging-web-9d1e9",
  storageBucket: "messaging-web-9d1e9",
  messagingSenderId: "996676983555",
  appId: "1:996676983555:web:885c8daed09ff95aae6736",
  measurementId: "G-0QGRKVEL19"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const messaging = getMessaging(app);

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/static/js/firebase-messaging-sw.js')
    .then((registration) => {
      console.log('Service Worker registration successful with scope: ', registration.scope);

      // Request permission to show notifications
      Notification.requestPermission()
        .then((permission) => {
          if (permission === 'granted') {
            console.log('Notification permission granted.');
            getToken(messaging, { vapidKey: 'BP2N9O0us4zsAVJ8QECLzJKfu_gNzwZoQ0kvxOwvekAlXtO_wE2tF-a3VvA5-xZ7m-A_ZRKBUW-xxTSu_yaqX6U' })
              .then((currentToken) => {
                if (currentToken) {
                  console.log('FCM Token:', currentToken);
                  saveTokenToServer(currentToken);
                } else {
                  console.warn('No registration token available. Request permission to generate one.');
                }
              })
              .catch((err) => {
                console.error('An error occurred while retrieving token. ', err);
              });
          } else {
            console.warn('Notification permission denied.');
          }
        });
    }).catch((err) => {
      console.log('Service Worker registration failed: ', err);
    });
}

function saveTokenToServer(token) {
  fetch('/register_device', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ token: token })
  }).then(response => {
    console.log('Token saved successfully:', response);
  }).catch(error => {
    console.error('Error saving token:', error);
  });
}

// Handle incoming messages
onMessage(messaging, (payload) => {
  console.log('Message received. ', payload);
  const notificationTitle = payload.notification.title;
  const notificationOptions = {
    body: payload.notification.body,
  };

  if (Notification.permission === 'granted') {
    new Notification(notificationTitle, notificationOptions);
  }
});
