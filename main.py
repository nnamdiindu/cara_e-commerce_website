import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, render_template, request, url_for, redirect, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, relationship
from flask_login import login_required, login_user, current_user, LoginManager, logout_user, UserMixin
from sqlalchemy import String, Integer, ForeignKey, Float, LargeBinary, select, DateTime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_bootstrap import Bootstrap5
from werkzeug.utils import secure_filename
from io import BytesIO
#Imports forms
from forms import AddCollection
from paystack_api import PaystackAPI

app = Flask(__name__)

load_dotenv()


# Paystack configuration
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY")
PAYSTACK_BASE_URL = "https://api.paystack.co"

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DB_URI")
app.secret_key = os.environ.get("SECRET_KEY")
bootstrap = Bootstrap5(app)
login_manager = LoginManager()
login_manager.init_app(app)


# Initialize Paystack API
paystack = PaystackAPI(PAYSTACK_SECRET_KEY)

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
db.init_app(app)


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    create_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationship to orders
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="user")


class StoreCollection(db.Model):
    __tablename__ = "store_collection"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    filename: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    mimetype: Mapped[str] = mapped_column(String(100), nullable=False)  # Fixed missing type annotation

    # Relationship to orders
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="collection")


class Order(db.Model):
    __tablename__ = "order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    reference: Mapped[str] = mapped_column(String(322), nullable=False)
    status: Mapped[str] = mapped_column(String(100), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Foreign keys
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    collection_id: Mapped[int] = mapped_column(Integer, ForeignKey("store_collection.id"), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="orders")
    collection: Mapped["StoreCollection"] = relationship("StoreCollection", back_populates="orders")


# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

with app.app_context():
    db.create_all()


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/collection_image/<int:collection_id>")
def serve_collection_image(collection_id):
    collection = db.get_or_404(StoreCollection, collection_id)
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
                flash("Collection updated successfully!")
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


@app.route("/checkout/<int:collection_id>")
def checkout_page(collection_id):
    selected_collection = db.get_or_404(StoreCollection, collection_id)

    return render_template("checkout.html",
                           collection=selected_collection,
                           paystack_key=PAYSTACK_SECRET_KEY)


@app.route("/process-payment", methods=["POST"])
def process_payment():
    """Handle payment processing"""
    if request.method == "POST":
        try:
            # Get form data
            email = request.form.get("email")
            collection_id = request.form.get("collection_id")
            quantity = int(request.form.get("quantity", 1))

            selected_collection = db.get_or_404(StoreCollection, collection_id)
            total_amount = selected_collection.amount * quantity

            # Initialize payment
            result = paystack.initialize_transaction(
                email=email,
                amount=total_amount
            )

            if result.get("status"):
                # Store order in database
                new_order = Order(
                    collection_id=collection_id,
                    email=email,
                    amount=total_amount,
                    reference=result["data"]["reference"],
                    status="pending",
                    user_id=current_user.id
                )
                db.session.add(new_order)
                db.session.commit()

                # Redirect to Paystack
                return redirect(result["data"]["authorization_url"])
            else:
                flash("Payment initialization failed. Please try again.")
                return redirect(url_for("checkout_page", collection_id=collection_id))

        except Exception as e:
            flash(f"Error: {str(e)}")
            return redirect(url_for("shop"))  # Your existing shop route


@app.route("/payment/callback")
def payment_callback():
    """Handle payment callback from Paystack"""
    reference = request.args.get("reference")

    if not reference:
        flash("Invalid payment reference")
        return redirect(url_for("shop"))

    # Verify payment
    result = paystack.verify_transaction(reference)

    if result.get("status") and result["data"]["status"] == "success":
        # Payment successful - update database
        order = db.session.execute(select(Order).where(Order.reference == reference)).scalar_one_or_none()
        if order:
            order.status = "completed"
            order.paid_at = datetime.now()
            db.session.commit()

        flash("Payment successful! Your order has been confirmed.")
        return render_template("success.html",
                               transaction=result["data"])
    else:
        flash("Payment failed. Please try again.")
        return render_template("payment_failed.html")


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



