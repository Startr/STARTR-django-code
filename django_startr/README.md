# Django Startr Smart Select + Other Amazing Features

This package enhances Django admin select fields with smart filtering capabilities.

## Features

- Converts the select fields in the Django admin to smart select fields, when you opt in
- Provides real-time filtering as you type
- Maintains all original select field functionality
- Gives the filter box the select's label, so a screen reader still hears the field's name

## Installation

1. Add `django_startr` to your `INSTALLED_APPS` in settings.py:

```python
INSTALLED_APPS = [
    ...
    'django_startr',
    ...
]
```

2. Import and add the settings from django_startr to your settings.py:

```python
from django_startr.settings import get_django_startr_settings

# Add the settings
settings_dict = get_django_startr_settings()
for key, value in settings_dict.items():
    globals()[key] = value
```

## Usage

Smart select is off by default. It swaps every single `<select>` in the admin for a text box, the changelist's action menu included, so a project chooses it. Turn it on in settings.py:

```python
STARTR_ADMIN_SMART_SELECT = True
```

Smart select ships with the admin skin, which has its own install order: `django_startr.admin_skin` before `django.contrib.admin`, `django_startr` after it. See the main README, "The admin skin".

## Customization

The smart select functionality can be customized by modifying the JavaScript in `django_startr/templatetags/smart_select.py`.

## Requirements

- Django 2.0 or higher
- Python 3.6 or higher 