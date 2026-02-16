<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${app_name}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="container">
        <h1>${app_name}</h1>
        <form action="{{ url_for('add') }}" method="post">
            <input type="text" name="item" placeholder="${input_placeholder}" required>
            <button type="submit">Add</button>
        </form>
        <ul>
            {% for item in items %}
            <li>
                {{ item }}
                <a href="{{ url_for('delete', item_id=loop.index0) }}" class="delete">✕</a>
            </li>
            {% endfor %}
        </ul>
    </div>
</body>
</html>
