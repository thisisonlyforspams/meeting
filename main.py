from flask import Flask, render_template, request, redirect

app = Flask(__name__)

meetings = []

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        title = request.form['title']
        date = request.form['date']
        time = request.form['time']
        brief = request.form['brief']
        minutes = request.form['minutes']
        meetings.append({
            'title': title,
            'date': date,
            'time': time,
            'brief': brief,
            'minutes': minutes
        })
        return redirect('/')
    return render_template('index.html', meetings=meetings)

if __name__ == '__main__':
    app.run(debug=True)
