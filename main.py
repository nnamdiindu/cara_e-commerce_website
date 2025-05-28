import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, url_for, redirect, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from flask_login import login_required, login_user, current_user, LoginManager, logout_user, UserMixin
from sqlalchemy import String, Integer, ForeignKey, Float, LargeBinary, select
from werkzeug.security import generate_password_hash, check_password_hash
from flask_bootstrap import Bootstrap5
from werkzeug.utils import secure_filename
from io import BytesIO
#Imports forms
from forms import AddCollection

app = Flask(__name__)

load_dotenv()

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DB_URI")
app.secret_key = os.environ.get("SECRET_KEY")
bootstrap = Bootstrap5(app)
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
db.init_app(app)

class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(50), nullable=False)

class StoreCollection(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    filename: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    mimetype = mapped_column(String(100), nullable=False)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

with app.app_context():
    db.create_all()


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/collection_image/<int:id>")
def serve_collection_image(id):
    collection = db.get_or_404(StoreCollection, id)
    return send_file(
        BytesIO(collection.data),
        mimetype=collection.mimetype,
        as_attachment=False
    )

@app.route("/shop")
def shop():
    collections = db.session.execute(db.select(StoreCollection)).scalars().all()
    return render_template("shop.html", collections=collections)


@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if user:
            flash("You've already signed up, please login.")
            return redirect(url_for("login"))

        hashed_and_salted_password = generate_password_hash(
            password=password,
            method="pbkdf2:sha256",
            salt_length=8
        )
        new_user = User(
            name=request.form.get("name"),
            email=request.form.get("email"),
            password=hashed_and_salted_password
        )
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for("home"))
    return render_template("register.html", current_user=current_user)


@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()

        if user:
            if check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for("home"))

            else:
                flash("Incorrect password, please try again.")
                return redirect(url_for("login"))
        else:
            flash("Email doesn't exist, please sign up.")
            return redirect(url_for("register"))

    return render_template("login.html", current_user=current_user)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

@app.route("/add-collection", methods=["GET", "POST"])
# @login_required
def add_collection():
    form = AddCollection()
    if form.validate_on_submit():
        file = request.files["image_file"]
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            try:
                # Create new collection record
                new_collection = StoreCollection(
                    brand_name=request.form.get("brand_name"),
                    description=request.form.get("description"),
                    filename=filename,
                    amount=float(request.form.get("amount")),
                    data=file.read(),  # Store actual image data
                    mimetype=file.mimetype
                )

                db.session.add(new_collection)
                db.session.commit()

                # flash("Collection added successfully!")
                return redirect(url_for("shop"))

            except ValueError:
                flash("Invalid amount value")
                return redirect(url_for("add_collection"))
            except Exception as e:
                flash(f"Error saving collection: {str(e)}")
                return redirect(url_for("add_collection"))
        else:
            flash("Invalid file type. Please upload an image file.")
            return redirect(url_for("add_collection"))

    return render_template("add_collections.html", form=form)


@app.route("/edit/<int:collection_id>", methods=["POST", "GET"])
@login_required
def edit_collection(collection_id):
    form = AddCollection()
    selected_collection = db.get_or_404(StoreCollection, collection_id)
    if form.validate_on_submit():
        if request.method == "POST":
            # Update collection data
            selected_collection.brand_name = request.form.get("brand_name", selected_collection.brand_name)
            selected_collection.description = request.form.get("description", selected_collection.description)

            try:
                selected_collection.amount = float(request.form.get("amount", selected_collection.amount))
            except ValueError:
                flash("Invalid amount value")
                return redirect(request.url)

            # Handle new image upload (optional)
            if "image_file" in request.files:
                file = request.files["image_file"]
                if file.filename != '' and file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    selected_collection.image = filename
                    selected_collection.data = file.read()
                    selected_collection.mimetype = file.mimetype
            try:
                db.session.commit()
                # flash('Collection updated successfully!')
                return redirect(url_for("shop"))
            except Exception as e:
                flash(f"Error updating collection: {str(e)}")
                return redirect(request.url)

    # Populating data of the selected cafe from the database
    form.brand_name.data = selected_collection.brand_name
    form.description.data = selected_collection.description
    form.amount.data = selected_collection.amount

    return render_template("add_collections.html", form=form)


@app.route("/delete_collection/<int:collection_id>", methods=["GET", "POST"])
@login_required
def delete_collection(collection_id):
    collection = db.get_or_404(StoreCollection, collection_id)
    try:
        db.session.delete(collection)
        db.session.commit()
        flash("Collection deleted successfully!")
    except Exception as e:
        flash(f"Error deleting collection: {str(e)}")
        return redirect(url_for("edit_collection"))

    return redirect(url_for("shop"))

@app.route("/blog")
def blog():
    return render_template("blog.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=True)



