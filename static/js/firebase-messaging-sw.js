// Import Firebase scripts from local paths
importScripts('/static/js/firebase-app.js');
importScripts('/static/js/firebase-messaging.js');

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

// Initialize Firebase in Service Worker
firebase.initializeApp(firebaseConfig);

const messaging = firebase.messaging();

messaging.onBackgroundMessage(function(payload) {
  console.log('Received background message ', payload);
  const notificationTitle = payload.notification.title;
  const notificationOptions = {
    body: payload.notification.body,
    icon: '/firebase-logo.png'
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});
