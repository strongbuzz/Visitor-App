import os
import re
from datetime import datetime, timedelta
from io import BytesIO

from bson import ObjectId
from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError

# ---------------------------------------------------------
# App / environment setup
# ---------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-key")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
MONGO_URI = os.getenv("MONGO_URI", "").strip()
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "VisitorDB")
MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME", "visitors")

# Existing records created before Multi-Site are treated as this site.
DEFAULT_SITE_NAME = os.getenv("DEFAULT_SITE_NAME", "Arizona Yard Office")
DEFAULT_SITE_SLUG = os.getenv("DEFAULT_SITE_SLUG", "arizona-yard-office")

if not MONGO_URI:
    raise RuntimeError(
        "MONGO_URI is not configured. "
        "Create a .env file from .env.example and paste your MongoDB Atlas connection string."
    )

mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = mongo_client[MONGO_DB_NAME]
visitors_collection = db[MONGO_COLLECTION_NAME]
sites_collection = db["sites"]


def verify_mongodb():
    """Fail fast if MongoDB cannot be reached."""
    mongo_client.admin.command("ping")


def ensure_indexes():
    """Small indexes that help the visitor/admin screens."""
    visitors_collection.create_index([("check_in", DESCENDING)])
    visitors_collection.create_index([("check_out", ASCENDING)])
    visitors_collection.create_index([("visitor_name", ASCENDING)])
    visitors_collection.create_index([("company", ASCENDING)])
    visitors_collection.create_index([("site_slug", ASCENDING)])
    sites_collection.create_index([("slug", ASCENDING)], unique=True)
    sites_collection.create_index([("active", ASCENDING), ("name", ASCENDING)])


# ---------------------------------------------------------
# Site helpers
# ---------------------------------------------------------
def slugify_site(value):
    """Convert a friendly site name into a URL-safe slug."""
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def serialize_site(doc):
    if not doc:
        return None
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name", ""),
        "slug": doc.get("slug", ""),
        "active": bool(doc.get("active", True)),
        "created_at": doc.get("created_at"),
    }


def ensure_default_site():
    """
    Create the current Arizona Yard Office site once.
    This also makes old visitor records (without site_slug) belong to the default site.
    """
    site = sites_collection.find_one({"slug": DEFAULT_SITE_SLUG})
    if site:
        return site

    now = datetime.now()
    try:
        sites_collection.insert_one(
            {
                "name": DEFAULT_SITE_NAME,
                "slug": DEFAULT_SITE_SLUG,
                "active": True,
                "created_at": now,
            }
        )
    except PyMongoError:
        # Another process may have created it at the same time.
        pass

    return sites_collection.find_one({"slug": DEFAULT_SITE_SLUG})


def get_site_by_slug(site_slug, active_only=True):
    if not site_slug:
        return None
    mongo_filter = {"slug": site_slug}
    if active_only:
        mongo_filter["active"] = True
    return sites_collection.find_one(mongo_filter)


def get_current_site():
    """Resolve the site for legacy '/' or '/checkout' visits."""
    ensure_default_site()

    last_slug = session.get("last_site_slug")
    if last_slug:
        site = get_site_by_slug(last_slug, active_only=True)
        if site:
            return site

    default_site = get_site_by_slug(DEFAULT_SITE_SLUG, active_only=True)
    if default_site:
        return default_site

    site = sites_collection.find_one({"active": True}, sort=[("name", ASCENDING)])
    if site:
        return site

    # Defensive fallback: there should always be at least one active site.
    default_site = ensure_default_site()
    if default_site and not default_site.get("active", True):
        sites_collection.update_one(
            {"_id": default_site["_id"]},
            {"$set": {"active": True}},
        )
        default_site["active"] = True
    return default_site


def require_public_site(site_slug):
    site = get_site_by_slug(site_slug, active_only=True)
    if not site:
        abort(404)
    session["last_site_slug"] = site["slug"]
    return site


def site_visitor_filter(site):
    """
    Filter visitors to one site.
    Old records without site_slug are treated as Arizona Yard Office.
    """
    if site["slug"] == DEFAULT_SITE_SLUG:
        return {
            "$or": [
                {"site_slug": DEFAULT_SITE_SLUG},
                {"site_slug": {"$exists": False}},
                {"site_slug": None},
            ]
        }
    return {"site_slug": site["slug"]}


def combine_filters(*parts):
    clean = [part for part in parts if part]
    if not clean:
        return {}
    if len(clean) == 1:
        return clean[0]
    return {"$and": clean}


# ---------------------------------------------------------
# General helpers
# ---------------------------------------------------------
def admin_required():
    return session.get("admin") is True


def to_object_id(value):
    try:
        return ObjectId(value)
    except Exception:
        return None


def display_datetime(value):
    """Admin UI: date + time without seconds."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return "-"


def export_date(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return ""


def export_time(value):
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    return ""


def serialize_visitor(doc):
    """Prepare MongoDB document for Jinja templates."""
    site_slug = doc.get("site_slug") or DEFAULT_SITE_SLUG
    site_name = doc.get("site_name") or DEFAULT_SITE_NAME

    return {
        "id": str(doc["_id"]),
        "company": doc.get("company", ""),
        "visitor_name": doc.get("visitor_name", ""),
        "host_name": doc.get("host_name", ""),
        "host_phone": doc.get("host_phone", ""),
        "purpose": doc.get("purpose", ""),
        "comment": doc.get("comment", ""),
        "checkout_comment": doc.get("checkout_comment", ""),
        "safety_agreed": bool(doc.get("safety_agreed", False)),
        "site_slug": site_slug,
        "site_name": site_name,
        "check_in": doc.get("check_in"),
        "check_out": doc.get("check_out"),
        "check_in_display": display_datetime(doc.get("check_in")),
        "check_out_display": display_datetime(doc.get("check_out")),
    }


def build_admin_filter(q="", date_from="", date_to="", status="", site_slug=""):
    filters = []

    if q:
        filters.append(
            {
                "$or": [
                    {"company": {"$regex": q, "$options": "i"}},
                    {"visitor_name": {"$regex": q, "$options": "i"}},
                    {"host_name": {"$regex": q, "$options": "i"}},
                    {"host_phone": {"$regex": q, "$options": "i"}},
                    {"purpose": {"$regex": q, "$options": "i"}},
                    {"comment": {"$regex": q, "$options": "i"}},
                    {"checkout_comment": {"$regex": q, "$options": "i"}},
                    {"site_name": {"$regex": q, "$options": "i"}},
                ]
            }
        )

    if date_from:
        try:
            start = datetime.strptime(date_from, "%Y-%m-%d")
            filters.append({"check_in": {"$gte": start}})
        except ValueError:
            pass

    if date_to:
        try:
            end = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            filters.append({"check_in": {"$lt": end}})
        except ValueError:
            pass

    if status == "inside":
        filters.append({"check_out": None})
    elif status == "checked_out":
        filters.append({"check_out": {"$ne": None}})

    if site_slug:
        site = get_site_by_slug(site_slug, active_only=False)
        if site:
            filters.append(site_visitor_filter(site))
        else:
            # Invalid site filter should return no records.
            filters.append({"_id": {"$exists": False}})

    return combine_filters(*filters)


@app.context_processor
def inject_helpers():
    return {
        "current_year": datetime.now().year,
    }


# ---------------------------------------------------------
# Visitor check-in
# ---------------------------------------------------------
@app.route("/", defaults={"site_slug": None}, methods=["GET", "POST"])
@app.route("/site/<site_slug>", methods=["GET", "POST"])
def register(site_slug):
    # Keep the old root URL working, but send it to the correct site URL.
    if site_slug is None:
        site = get_current_site()
        if not site:
            abort(404)
        return redirect(url_for("register", site_slug=site["slug"]))

    site = require_public_site(site_slug)
    current_site = serialize_site(site)

    if request.method == "POST":
        company = request.form.get("company", "").strip()
        visitor_name = request.form.get("visitor_name", "").strip()
        host_name = request.form.get("host_name", "").strip()
        host_phone = request.form.get("host_phone", "").strip()
        purpose = request.form.get("purpose", "").strip()
        comment = request.form.get("comment", "").strip()
        safety_agreed = request.form.get("safety_agreed") == "on"

        if not company or not visitor_name or not host_name or not purpose:
            flash("Please complete all required fields.", "error")
            return render_template("register.html", current_site=current_site)

        if not safety_agreed:
            flash(
                "You must agree to the Safety Guidelines before check-in.",
                "error",
            )
            return render_template("register.html", current_site=current_site)

        now = datetime.now()

        try:
            visitors_collection.insert_one(
                {
                    "company": company,
                    "visitor_name": visitor_name,
                    "host_name": host_name,
                    "host_phone": host_phone,
                    "purpose": purpose,
                    "comment": comment,
                    "safety_agreed": True,
                    "site_slug": site["slug"],
                    "site_name": site["name"],
                    "check_in": now,
                    "check_out": None,
                }
            )
        except PyMongoError as exc:
            app.logger.exception("MongoDB insert failed")
            flash(f"Could not save the visitor record: {exc}", "error")
            return render_template("register.html", current_site=current_site)

        return render_template(
            "checkin_success.html",
            visitor_name=visitor_name,
            check_in=now.strftime("%Y-%m-%d %H:%M"),
            current_site=current_site,
            site_name=site["name"],
            site_slug=site["slug"],
        )

    return render_template("register.html", current_site=current_site)


# ---------------------------------------------------------
# Visitor self-service check-out
# ---------------------------------------------------------
@app.route("/checkout", defaults={"site_slug": None}, methods=["GET", "POST"])
@app.route("/site/<site_slug>/checkout", methods=["GET", "POST"])
def visitor_checkout(site_slug):
    if site_slug is None:
        site = get_current_site()
        if not site:
            abort(404)
        return redirect(url_for("visitor_checkout", site_slug=site["slug"]))

    site = require_public_site(site_slug)
    current_site = serialize_site(site)
    query = request.form.get("query", "").strip() if request.method == "POST" else ""

    filters = [{"check_out": None}, site_visitor_filter(site)]

    if query:
        filters.append(
            {
                "$or": [
                    {"visitor_name": {"$regex": query, "$options": "i"}},
                    {"company": {"$regex": query, "$options": "i"}},
                ]
            }
        )

    mongo_filter = combine_filters(*filters)

    try:
        docs = list(
            visitors_collection.find(mongo_filter)
            .sort("check_in", DESCENDING)
            .limit(100)
        )
    except PyMongoError as exc:
        app.logger.exception("MongoDB checkout search failed")
        flash(f"Could not load visitor records: {exc}", "error")
        docs = []

    results = [serialize_visitor(doc) for doc in docs]

    if request.method == "POST" and query and not results:
        flash("No active visitor record was found.", "error")

    return render_template(
        "visitor_checkout.html",
        results=results,
        query=query,
        current_site=current_site,
    )


@app.post("/checkout/confirm/<visitor_id>", defaults={"site_slug": None})
@app.post("/site/<site_slug>/checkout/confirm/<visitor_id>")
def visitor_checkout_confirm(visitor_id, site_slug):
    if site_slug is None:
        site = get_current_site()
    else:
        site = get_site_by_slug(site_slug, active_only=True)

    if not site:
        abort(404)

    session["last_site_slug"] = site["slug"]
    current_site = serialize_site(site)
    object_id = to_object_id(visitor_id)

    if not object_id:
        flash("Invalid visitor record.", "error")
        return redirect(url_for("visitor_checkout", site_slug=site["slug"]))

    visitor_filter = combine_filters(
        {"_id": object_id, "check_out": None},
        site_visitor_filter(site),
    )

    try:
        visitor = visitors_collection.find_one(visitor_filter)

        if not visitor:
            flash(
                "This visitor has already checked out, belongs to another site, or was not found.",
                "error",
            )
            return redirect(url_for("visitor_checkout", site_slug=site["slug"]))

        now = datetime.now()
        checkout_comment = request.form.get("checkout_comment", "").strip()[:1000]

        result = visitors_collection.update_one(
            visitor_filter,
            {
                "$set": {
                    "check_out": now,
                    "checkout_comment": checkout_comment,
                }
            },
        )

        if not result.modified_count:
            flash("This visitor has already checked out.", "error")
            return redirect(url_for("visitor_checkout", site_slug=site["slug"]))
    except PyMongoError as exc:
        app.logger.exception("MongoDB checkout update failed")
        flash(f"Could not complete check-out: {exc}", "error")
        return redirect(url_for("visitor_checkout", site_slug=site["slug"]))

    return render_template(
        "checkout_success.html",
        visitor_name=visitor.get("visitor_name", ""),
        company=visitor.get("company", ""),
        check_out=now.strftime("%Y-%m-%d %H:%M"),
        current_site=current_site,
        site_name=site["name"],
        site_slug=site["slug"],
    )


# ---------------------------------------------------------
# Admin authentication
# ---------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")

        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))

        flash("Incorrect password.", "error")

    return render_template("login.html", login_error=request.method == "POST")


@app.route("/admin/logout")
def admin_logout():
    # Keep the last-site selection for the kiosk redirect after logout.
    last_site_slug = session.get("last_site_slug")
    session.clear()
    if last_site_slug:
        session["last_site_slug"] = last_site_slug
    return redirect(url_for("admin_login"))


# ---------------------------------------------------------
# Admin site management
# ---------------------------------------------------------
@app.post("/admin/sites/add")
def admin_add_site():
    if not admin_required():
        return redirect(url_for("admin_login"))

    name = request.form.get("site_name", "").strip()
    requested_slug = request.form.get("site_slug", "").strip()
    slug = slugify_site(requested_slug or name)

    if not name:
        flash("Site name is required.", "error")
        return redirect(url_for("admin"))

    if not slug:
        flash("Enter an English URL Name, for example: yard-3.", "error")
        return redirect(url_for("admin"))

    if sites_collection.find_one({"slug": slug}):
        flash("That Site URL already exists. Please use a different URL Name.", "error")
        return redirect(url_for("admin"))

    try:
        sites_collection.insert_one(
            {
                "name": name,
                "slug": slug,
                "active": True,
                "created_at": datetime.now(),
            }
        )
        flash(f"Site added: {name}", "success")
    except PyMongoError as exc:
        app.logger.exception("MongoDB site insert failed")
        flash(f"Could not add the site: {exc}", "error")

    return redirect(url_for("admin"))


@app.post("/admin/sites/<site_id>/toggle")
def admin_toggle_site(site_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    object_id = to_object_id(site_id)
    if not object_id:
        flash("Invalid site.", "error")
        return redirect(url_for("admin"))

    site = sites_collection.find_one({"_id": object_id})
    if not site:
        flash("Site not found.", "error")
        return redirect(url_for("admin"))

    new_active = not bool(site.get("active", True))

    if not new_active:
        active_count = sites_collection.count_documents({"active": True})
        if active_count <= 1:
            flash("At least one site must remain active.", "error")
            return redirect(url_for("admin"))

    try:
        sites_collection.update_one(
            {"_id": object_id},
            {"$set": {"active": new_active}},
        )
        state = "activated" if new_active else "deactivated"
        flash(f"{site.get('name', 'Site')} {state}.", "success")
    except PyMongoError as exc:
        app.logger.exception("MongoDB site toggle failed")
        flash(f"Could not update the site: {exc}", "error")

    return redirect(url_for("admin"))


# ---------------------------------------------------------
# Admin visitor list
# ---------------------------------------------------------
@app.route("/admin")
def admin():
    if not admin_required():
        return redirect(url_for("admin_login"))

    ensure_default_site()

    q = request.args.get("q", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    status = request.args.get("status", "").strip()
    site_slug = request.args.get("site", "").strip()

    mongo_filter = build_admin_filter(
        q=q,
        date_from=date_from,
        date_to=date_to,
        status=status,
        site_slug=site_slug,
    )

    try:
        docs = list(
            visitors_collection.find(mongo_filter)
            .sort("check_in", DESCENDING)
            .limit(1000)
        )
        site_docs = list(sites_collection.find().sort([("active", DESCENDING), ("name", ASCENDING)]))
    except PyMongoError as exc:
        app.logger.exception("MongoDB admin query failed")
        flash(f"Could not load records: {exc}", "error")
        docs = []
        site_docs = []

    visitors = [serialize_visitor(doc) for doc in docs]
    sites = [serialize_site(doc) for doc in site_docs]

    return render_template(
        "admin.html",
        visitors=visitors,
        sites=sites,
        q=q,
        date_from=date_from,
        date_to=date_to,
        status=status,
        selected_site=site_slug,
    )


@app.post("/admin/checkout/<visitor_id>")
def admin_checkout(visitor_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    object_id = to_object_id(visitor_id)

    if not object_id:
        flash("Invalid visitor record.", "error")
        return redirect(url_for("admin"))

    try:
        result = visitors_collection.update_one(
            {"_id": object_id, "check_out": None},
            {"$set": {"check_out": datetime.now()}},
        )

        if result.modified_count:
            flash("Visitor checked out successfully.", "success")
        else:
            flash("Visitor is already checked out or was not found.", "error")

    except PyMongoError as exc:
        app.logger.exception("MongoDB admin checkout failed")
        flash(f"Could not complete check-out: {exc}", "error")

    return redirect(request.referrer or url_for("admin"))


# ---------------------------------------------------------
# Excel export
# ---------------------------------------------------------
@app.route("/admin/export")
def export_excel():
    if not admin_required():
        return redirect(url_for("admin_login"))

    q = request.args.get("q", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    status = request.args.get("status", "").strip()
    site_slug = request.args.get("site", "").strip()

    mongo_filter = build_admin_filter(
        q=q,
        date_from=date_from,
        date_to=date_to,
        status=status,
        site_slug=site_slug,
    )

    try:
        docs = list(visitors_collection.find(mongo_filter).sort("check_in", DESCENDING))
    except PyMongoError as exc:
        app.logger.exception("MongoDB export query failed")
        flash(f"Could not export visitor records: {exc}", "error")
        return redirect(url_for("admin"))

    wb = Workbook()
    ws = wb.active
    ws.title = "Visitors"

    headers = [
        "ID",
        "Site",
        "Company",
        "Visitor Name",
        "Host Name",
        "Host Phone",
        "Purpose",
        "Comment",
        "Check Out Comment / Issue",
        "Safety Agreed",
        "Check In Date",
        "Check In Time",
        "Check Out Date",
        "Check Out Time",
    ]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="003A70")
        cell.alignment = Alignment(horizontal="center")

    for doc in docs:
        ws.append(
            [
                str(doc["_id"]),
                doc.get("site_name") or DEFAULT_SITE_NAME,
                doc.get("company", ""),
                doc.get("visitor_name", ""),
                doc.get("host_name", ""),
                doc.get("host_phone", ""),
                doc.get("purpose", ""),
                doc.get("comment", ""),
                doc.get("checkout_comment", ""),
                "Yes" if doc.get("safety_agreed") else "No",
                export_date(doc.get("check_in")),
                export_time(doc.get("check_in")),
                export_date(doc.get("check_out")),
                export_time(doc.get("check_out")),
            ]
        )

    widths = {
        "A": 26,
        "B": 24,
        "C": 24,
        "D": 22,
        "E": 22,
        "F": 18,
        "G": 24,
        "H": 36,
        "I": 40,
        "J": 16,
        "K": 16,
        "L": 16,
        "M": 16,
        "N": 16,
    }

    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"visitor_list_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------
# Start application
# ---------------------------------------------------------
if __name__ == "__main__":
    try:
        verify_mongodb()
        ensure_indexes()
        ensure_default_site()
        print("MongoDB connection: OK")
        print(f"Database: {MONGO_DB_NAME}")
        print(f"Collection: {MONGO_COLLECTION_NAME}")
        print("Sites collection: sites")
    except Exception as exc:
        print("\nMongoDB connection failed.")
        print(exc)
        print("\nCheck MONGO_URI in your .env file and Atlas Network Access settings.")
        raise

    app.run(host="0.0.0.0", port=5000, debug=True)
