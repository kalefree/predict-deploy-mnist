from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import List
import numpy as np
import cv2
from PIL import Image
import tflite_runtime.interpreter as tflite

model = tflite.Interpreter("static/mnist.tflite")
model.allocate_tensors()

input_details = model.get_input_details()
output_details = model.get_output_details()

class_mapping = {0: 'zero',
                 1: 'one',
                 2: 'two',
                 3: 'three',
                 4: 'four',
                 5: 'five',
                 6: 'six',
                 7: 'seven',
                 8: 'eight',
                 9: 'nine'
                 }


def model_predict(images_arr):
    predictions = [0] * len(images_arr)

    for i, val in enumerate(predictions):
        model.set_tensor(input_details[0]['index'], images_arr[i].reshape((1, 28, 28, 1)))
        model.invoke()
        predictions[i] = model.get_tensor(output_details[0]['index']).reshape((10,))

    prediction_probabilities = np.array(predictions)
    argmaxs = np.argmax(prediction_probabilities, axis=1)

    return argmaxs


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


def resize(image):
    return cv2.resize(image, (28, 28))

#Expects image in grey
def resize_to_contour(image, plt=None):
    ret, thresh = cv2.threshold(image.copy(), 75, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    preprocessed_digits = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)

        # Creating a rectangle around the digit in the original image (for displaying the digits fetched via contours)
        cv2.rectangle(image, (x, y), (x + w, y + h), color=(0, 255, 0), thickness=2)

        # Cropping out the digit from the image corresponding to the current contours in the for loop
        digit = thresh[y:y + h, x:x + w]

        # Resizing that digit to (18, 18)
        resized_digit = cv2.resize(digit, (18, 18))

        # Padding the digit with 5 pixels of black color (zeros) in each side to finally produce the image of (28, 28)
        padded_digit = np.pad(resized_digit, ((5, 5), (5, 5)), "constant", constant_values=0)

        # Adding the preprocessed digit to the list of preprocessed digits
        preprocessed_digits.append(padded_digit)
    return preprocessed_digits[-1]

@app.post("/uploadfiles/", response_class=HTMLResponse)
async def create_upload_files(files: List[UploadFile] = File(...)):
    images = []
    for file in files:
        f = await file.read()
        images.append(f)

    images = [np.frombuffer(img, np.uint8) for img in images]
    images_grey = [cv2.imdecode(img, 0) for img in images]
    images_resized = [resize_to_contour(img) for img in images_grey]

    names = [file.filename for file in files]

    for image, name in zip(images_resized, names):
        pillow_image = Image.fromarray(image)
        pillow_image.save('static/' + name)

    image_paths = ['static/' + name for name in names]

    images_arr = np.array(images_resized, dtype=np.float32)

    class_indexes = model_predict(images_arr)

    class_predictions = [class_mapping[x] for x in class_indexes]

    column_labels = ["Image", "Prediction"]

    table_html = get_html_table(image_paths, class_predictions, column_labels)

    content = head_html + """
    <marquee width="525" behavior="alternate"><h1 style="color:red;font-family:Arial">Here's what the computer reads!</h1></marquee>
    """ + str(table_html) + '''<br><form method="post" action="/">
    <button type="submit">Home</button>
    </form>'''

    return content


@app.post("/", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def main():
    content = head_html + """
    <marquee width="725" behavior="alternate"><h1 style="color:red;font-family:Arial"> Please upload your images below</h1></marquee>
    <h3 style="font-family:Arial">Let's discover what numbers the computer will read</h3><br>
    """

    original_paths = [   'zero.jpg',
                         'one.jpg',
                         'two.jpg',
                         'three.jpg',
                         'four.jpg',
                         'five.jpg',
                         'six.jpg',
                         'seven.jpg',
                         'eight.jpg',
                         'nine.jpg',
                      ]

    full_original_paths = ['static/original/' + x for x in original_paths]

    display_names = [filename.split('.')[0] for filename in original_paths]

    column_labels = []

    content = content + get_html_table(full_original_paths, display_names, column_labels)

    content = content + """
    <br/>
    <br/>
    <form  action="/uploadfiles/" enctype="multipart/form-data" method="post">
    <input name="files" type="file" multiple>
    <input type="submit">
    </form>
    </body>
    """

    return content


head_html = """
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
</head>
<body style="background-color:powderblue;">
<center>
"""


def get_html_table(image_paths, names, column_labels):
    s = '<table align="center">'
    if column_labels:
        s += '<tr><th><h4 style="font-family:Arial">' + column_labels[
            0] + '</h4></th><th><h4 style="font-family:Arial">' + column_labels[1] + '</h4></th></tr>'

    for name, image_path in zip(names, image_paths):
        s += '<tr><td><img height="80" src="/' + image_path + '" ></td>'
        s += '<td style="text-align:center">' + name + '</td></tr>'
    s += '</table>'

    return s