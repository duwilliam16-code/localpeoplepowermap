from flask import Flask, render_template, request, jsonify
import sqlite3
import json

app = Flask(__name__)
DB_PATH = "database.db"
MAX_TAGS = 50


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    existing = conn.execute("PRAGMA table_info(resources)").fetchall()
    columns = [col[1] for col in existing]
    if existing and "details" not in columns:
        conn.execute("DROP TABLE resources")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            tags TEXT,
            email TEXT,
            phone TEXT,
            website TEXT,
            address TEXT,
            notes TEXT,
            details TEXT
        )
    """)
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
    if count == 0:
        samples = [
            ("City Park", "location",
             "Large outdoor space with pavilions and parking",
             "outdoor,venue,park,event,space,parking,pavilion",
             "", "555-010-0001", "", "123 Park Ave",
             "Available weekends, permit required",
             json.dumps({
                 "capacity": "500 people",
                 "indoor_outdoor": "outdoor",
                 "rental_cost": "Free with permit",
                 "permit_required": "Yes — City Parks permit required",
                 "parking": "Large free lot on site",
                 "amenities": ["restrooms", "pavilion", "picnic tables", "electricity", "grill stations", "playground"]
             })),
            ("Downtown Community Center", "location",
             "Indoor venue with kitchen and seating for 200",
             "indoor,venue,kitchen,tables,chairs,seating,projector",
             "community@example.com", "555-010-0002", "", "456 Main St",
             "Rental fee applies. Book 2 weeks in advance.",
             json.dumps({
                 "capacity": "200 people",
                 "indoor_outdoor": "indoor",
                 "rental_cost": "$150/day",
                 "permit_required": "No",
                 "parking": "Street parking and nearby garage",
                 "amenities": ["commercial kitchen", "tables", "chairs", "projector", "wifi", "stage", "ADA accessible"]
             })),
            ("Marcus Johnson", "person",
             "Event DJ with 5 years experience",
             "dj,music,entertainment,sound,audio,hype,emcee",
             "marcus@example.com", "555-020-0001", "", "",
             "Books up fast — contact early",
             json.dumps({
                 "hometown": "Memphis, TN",
                 "availability": "Weekends and evenings",
                 "organizations": ["Local DJ Guild", "Musicians Union"],
                 "affiliations": ["Community Arts Council"],
                 "skills": ["djing", "emceeing", "sound setup", "crowd engagement", "event hosting"]
             })),
            ("Fresh Catering Co.", "business",
             "Local catering company specializing in BBQ and soul food",
             "food,catering,bbq,cookout,soul food,plates,grill",
             "fresh@example.com", "555-030-0001", "freshcatering.example.com", "789 Oak Blvd", "",
             json.dumps({
                 "cost": "Starting at $15/plate",
                 "capacity": "Up to 500 guests",
                 "hours": "Available 7 days a week",
                 "parking": "Mobile setup — comes to you",
                 "services": ["bbq", "soul food", "setup", "cleanup", "servers", "vegetarian options", "desserts"]
             })),
            ("Banner Bros Printing", "business",
             "Local print shop for flyers, banners, and signs",
             "flyers,printing,marketing,promotion,banners,signs,design",
             "banners@example.com", "555-030-0002", "", "321 Print Ln",
             "24hr turnaround available",
             json.dumps({
                 "cost": "Flyers from $0.10 each, banners from $25",
                 "capacity": "No limit on orders",
                 "hours": "Mon–Sat 8am–7pm",
                 "parking": "Free parking in front",
                 "services": ["flyers", "banners", "yard signs", "t-shirts", "graphic design", "bulk printing"]
             })),
            ("Keisha Williams", "person",
             "Experienced event coordinator and volunteer organizer",
             "coordinator,planning,logistics,volunteer,organization,scheduling",
             "keisha@example.com", "555-020-0002", "", "",
             "Available for consulting and day-of coordination",
             json.dumps({
                 "hometown": "Atlanta, GA",
                 "availability": "Flexible — book 3 weeks ahead",
                 "organizations": ["Community Action Network", "Women in Leadership ATL"],
                 "affiliations": ["City Council Advisory Board", "Neighborhood Association"],
                 "skills": ["event planning", "volunteer coordination", "budgeting", "vendor management", "community outreach"]
             })),
            ("Sunrise Rentals", "business",
             "Rents tables, chairs, tents, and equipment",
             "rentals,tables,chairs,tents,equipment,setup,teardown",
             "sunrise@example.com", "555-030-0003", "", "",
             "Delivery available",
             json.dumps({
                 "cost": "Tables $8/ea, Chairs $2/ea, Tents from $150",
                 "capacity": "Stock for up to 1000 guests",
                 "hours": "Mon–Sun 7am–8pm",
                 "parking": "Warehouse pickup or delivery",
                 "services": ["table rental", "chair rental", "tent rental", "delivery", "setup", "teardown", "linens", "lighting"]
             })),
            ("Channel 5 News", "business",
             "Local TV news station for event promotion",
             "media,press,promotion,publicity,news,tv,coverage",
             "news@example.com", "555-030-0004", "", "1 Broadcast Plaza",
             "Submit press releases 2 weeks ahead",
             json.dumps({
                 "cost": "Free coverage (press release) or paid ads",
                 "capacity": "Citywide reach",
                 "hours": "Newsroom open 24/7",
                 "parking": "N/A",
                 "services": ["news coverage", "press releases", "paid advertising", "social media promotion", "community calendar listing"]
             })),
        ]
        conn.executemany(
            "INSERT INTO resources (name, type, description, tags, email, phone, website, address, notes, details) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            samples
        )
        conn.commit()
    conn.close()


def parse_tags(raw):
    if not raw:
        return []
    tags = [t.strip().lower() for t in raw.split(",") if t.strip()]
    return tags[:MAX_TAGS]


def enrich_resource(r):
    resource = dict(r)
    resource["tag_list"] = parse_tags(resource.get("tags", ""))
    try:
        resource["details"] = json.loads(resource.get("details") or "{}")
    except (json.JSONDecodeError, TypeError):
        resource["details"] = {}
    # Parse any tag lists inside details
    for key in ["organizations", "affiliations", "skills", "amenities", "services"]:
        val = resource["details"].get(key, [])
        if isinstance(val, str):
            resource["details"][key] = parse_tags(val)
        elif isinstance(val, list):
            resource["details"][key] = val[:MAX_TAGS]
    return resource


def search_resources(goal):
    keywords = goal.lower().split()
    conn = get_db()
    all_resources = conn.execute("SELECT * FROM resources").fetchall()
    conn.close()

    scored = []
    for r in all_resources:
        resource = enrich_resource(r)
        details_text = " ".join([
            str(v) for v in resource["details"].values()
            if isinstance(v, (str, list))
        ]).lower()
        searchable = f"{resource['name']} {resource['description']} {resource['tags']} {details_text}".lower()
        score = sum(1 for word in keywords if word in searchable)
        if score > 0:
            scored.append((score, resource))

    scored.sort(reverse=True, key=lambda x: x[0])
    return [item for _, item in scored]


def build_checklist(goal, resources):
    checklist = [
        "Define your event goal and target audience",
        "Set a date and time for the event",
        "Set a budget",
    ]
    types_found = {r["type"] for r in resources}
    if "location" in types_found:
        checklist.append("Book a venue from your matched locations")
    else:
        checklist.append("Find and book a venue")
    if "business" in types_found or "person" in types_found:
        checklist.append("Reach out to matched contacts and vendors")
    checklist += [
        "Confirm all vendors and volunteers",
        "Promote the event (flyers, social media, word of mouth)",
        "Confirm headcount and finalize logistics",
        "Execute the event",
        "Follow up with attendees and document outcomes",
    ]
    return checklist


def build_flowchart(resources):
    lines = ["graph TD"]
    lines.append('    A["Define Goal"] --> B["Set Date & Budget"]')
    lines.append('    B --> C["Book Venue"]')
    locations = [r for r in resources if r["type"] == "location"]
    people = [r for r in resources if r["type"] == "person"]
    businesses = [r for r in resources if r["type"] == "business"]
    for i, loc in enumerate(locations[:2]):
        lines.append(f'    C --> L{i}["{loc["name"]}"]')
    lines.append('    B --> D["Hire Vendors & People"]')
    for i, p in enumerate(people[:2]):
        lines.append(f'    D --> P{i}["{p["name"]}"]')
    for i, b in enumerate(businesses[:3]):
        lines.append(f'    D --> BZ{i}["{b["name"]}"]')
    lines.append('    D --> E["Promote Event"]')
    lines.append('    E --> F["Execute Event"]')
    lines.append('    F --> G["Follow Up"]')
    return "\n".join(lines)


def build_details(data, resource_type):
    if resource_type == "person":
        return {
            "hometown": data.get("hometown", ""),
            "availability": data.get("availability", ""),
            "organizations": parse_tags(data.get("organizations", "")),
            "affiliations": parse_tags(data.get("affiliations", "")),
            "skills": parse_tags(data.get("skills", "")),
        }
    elif resource_type == "business":
        return {
            "cost": data.get("cost", ""),
            "capacity": data.get("capacity", ""),
            "hours": data.get("hours", ""),
            "parking": data.get("parking", ""),
            "services": parse_tags(data.get("services", "")),
        }
    elif resource_type == "location":
        return {
            "capacity": data.get("capacity", ""),
            "indoor_outdoor": data.get("indoor_outdoor", ""),
            "rental_cost": data.get("rental_cost", ""),
            "permit_required": data.get("permit_required", ""),
            "parking": data.get("parking", ""),
            "amenities": parse_tags(data.get("amenities", "")),
        }
    return {}


@app.route("/")
def root():
    from flask import redirect
    return redirect("/lpmt")


@app.route("/lpmt")
def index():
    return render_template("index.html")


@app.route("/lpmt/plan", methods=["POST"])
def plan():
    goal = request.form.get("goal", "").strip()
    if not goal:
        return jsonify({"error": "Please enter a goal."})
    resources = search_resources(goal)
    checklist = build_checklist(goal, resources)
    flowchart = build_flowchart(resources)
    return jsonify({"resources": resources, "checklist": checklist, "flowchart": flowchart})


@app.route("/lpmt/resources")
def list_resources():
    conn = get_db()
    all_resources = conn.execute("SELECT * FROM resources ORDER BY type, name").fetchall()
    conn.close()
    return render_template("resources.html", resources=[enrich_resource(r) for r in all_resources], max_tags=MAX_TAGS)


@app.route("/lpmt/resource/<int:resource_id>")
def get_resource(resource_id):
    conn = get_db()
    r = conn.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
    conn.close()
    if not r:
        return jsonify({"error": "Not found"}), 404
    return jsonify(enrich_resource(r))


@app.route("/lpmt/add", methods=["POST"])
def add_resource():
    data = request.form
    resource_type = data.get("type", "")
    tags = ",".join(parse_tags(data.get("tags", "")))
    conn = get_db()
    conn.execute(
        "INSERT INTO resources (name, type, description, tags, email, phone, website, address, notes, details) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data["name"], resource_type, data["description"], tags,
         data.get("email", ""), data.get("phone", ""),
         data.get("website", ""), data.get("address", ""),
         data.get("notes", ""), json.dumps(build_details(data, resource_type)))
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/lpmt/edit/<int:resource_id>", methods=["POST"])
def edit_resource(resource_id):
    data = request.form
    resource_type = data.get("type", "")
    tags = ",".join(parse_tags(data.get("tags", "")))
    conn = get_db()
    conn.execute(
        """UPDATE resources SET name=?, type=?, description=?, tags=?,
           email=?, phone=?, website=?, address=?, notes=?, details=?
           WHERE id=?""",
        (data["name"], resource_type, data["description"], tags,
         data.get("email", ""), data.get("phone", ""),
         data.get("website", ""), data.get("address", ""),
         data.get("notes", ""), json.dumps(build_details(data, resource_type)),
         resource_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/lpmt/delete/<int:resource_id>", methods=["POST"])
def delete_resource(resource_id):
    conn = get_db()
    conn.execute("DELETE FROM resources WHERE id = ?", (resource_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
