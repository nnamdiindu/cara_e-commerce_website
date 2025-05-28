from flask_wtf import FlaskForm
from wtforms.fields.simple import StringField, FileField, SubmitField
from wtforms.validators import DataRequired


class AddCollection(FlaskForm):
    brand_name = StringField("Brand Name", validators=[DataRequired()])
    description = StringField("Description", validators=[DataRequired()])
    image_file = FileField("Upload image", validators=[DataRequired()])
    amount = StringField("Amount", validators=[DataRequired()])
    submit = SubmitField("Add")




