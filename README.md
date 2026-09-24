# Visitor Registration App - MongoDB Version

This version no longer uses SQLite.

Architecture:

iPad / PC Browser
        |
        v
Flask App (Python)
        |
        v
MongoDB Atlas

## Included features

- Visitor check-in
- Visitor self check-out
- Check-out page automatically shows all Gate In visitors
- Search by visitor name or company
- Admin login
- Admin search / date / status filtering
- Admin check-out
- Excel export
- Check In Date / Check In Time separated in Excel
- Check Out Date / Check Out Time separated in Excel
- Admin screen hides seconds
- Dark blue FNS logo block
- MongoDB Atlas storage

## 1. MongoDB Atlas

Since you already connected Atlas to Compass, use the SAME Atlas cluster.

In Atlas:

Connect -> Drivers -> Python

Copy the connection string.

Example only:

mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority

DO NOT share the real string with other people.

## 2. Create the .env file

Inside this project folder you will see:

.env.example

Make a COPY of it and rename the copy:

.env

Open `.env` and replace this:

MONGO_URI=mongodb+srv://YOUR_USERNAME:YOUR_PASSWORD@YOUR_CLUSTER.mongodb.net/?retryWrites=true&w=majority

with your real Atlas connection string.

Example:

MONGO_URI=mongodb+srv://jinwoo:MyPassword123@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority

Important:
If your MongoDB password contains characters such as @, :, /, ?, #, [, ], they may need URL encoding.
The easiest option for testing is to create a database password using letters/numbers.

Also change:

ADMIN_PASSWORD=admin123

to your preferred admin password.

## 3. Atlas Network Access

Atlas must allow the IP address of the PC running Flask.

Atlas:
Security -> Network Access

Add the current public IP address of your PC.

For testing, Atlas also has "Allow access from anywhere", but that is less secure and should not be the production setting.

## 4. Start

Double-click:

run_windows.bat

The first run installs:

- Flask
- pymongo
- python-dotenv
- openpyxl

If MongoDB connects successfully, the command window will show:

MongoDB connection: OK
Database: VisitorDB
Collection: visitors

Then:

Visitor Check In
http://127.0.0.1:5000

Visitor Check Out
http://127.0.0.1:5000/checkout

Admin
http://127.0.0.1:5000/admin

## 5. Check MongoDB Compass

After registering a test visitor:

Database:
VisitorDB

Collection:
visitors

You should see a document similar to:

{
  "_id": ObjectId(...),
  "company": "ABC",
  "visitor_name": "John Kim",
  "host_name": "Jinwoo Lee",
  "host_phone": "480-555-1234",
  "purpose": "Yard Visit",
  "comment": "",
  "safety_agreed": true,
  "check_in": ISODate(...),
  "check_out": null
}

After Check Out, check_out becomes a date.

## 6. Important difference from SQLite

OLD:
Flask -> visitors.db file

NEW:
Flask -> MongoDB Atlas -> VisitorDB -> visitors collection

There is no `visitors.db` file in this version.

## 7. iPad

When Flask is running on your PC, find the PC IPv4 address:

ipconfig

For example:

10.86.99.192

If the iPad is allowed to reach the PC over the company network:

http://10.86.99.192:5000

The company Wi-Fi/firewall may block device-to-device traffic even if both devices are on the same Wi-Fi.

## Production note

This is still a prototype/development deployment.
Before storing real company visitor information, confirm company policy for:

- MongoDB Atlas / external cloud storage
- personal information
- HTTPS
- authentication
- backup / retention
- server deployment
