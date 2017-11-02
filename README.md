# jimd - jinja2 templates and markdown for static websites

Jimd is an extremely simple static web site generator.
It provides
* Managing jinja2 templates for html layout
* Injecting markdown content into the templates
* A built-in webserver for previewing page content
* A mechanism for detecting changes in content files in order to compile them in the background
* A rudimentary plugin architecture

## Installation

Clone this repository.

## Synopsis

Create a project
```
python jimd.py create
```

Build a project
```
python jimd.py build
```

Preview a project and monitor changes
```
python jimd.py preview
```

## Folders

Output folder
```
/build
```

Template folder
```
/templates
```

Content folder
```
/content
```

Plugin folder
```
/plugins
```

## Templates

Jinja2 templates can be put into the templates folder in order to be used by content pages.
The templates are loaded drectly by jinja2, so inheritance etc. works.

## Content
Files in the content folder are processed in two different ways.
If the file is not a markdown file (i.e. it does not have a .md extension),
it is copied to the build folder.
If it is a markdown file, the appropriate template is loaded as indicated by the metadata
in the markdown file.
For example,
```
template: page.html

# My markdown page

yada yada yada
```
will select page.html as the template for this markdown page.
If no template is specified, base.html will be tried as a template.
The markdown content is then rendered into the {{ content }} variable in the jinja2 template
and the result is placed into the build folder, with the extension of the markdown file renamed to .html.

Variables defined in the meta part of the markdown pages can be accessed in the jinja2 template.
For example,
```
title: My title

# My markdown page

yada yada yada
```

can be used in the jinja2 template the following way:

```
<html lang="en">
  <head>
    <title>{{ title }}</title>
  </head>
  <body>
    {{ content }}
  </body>
</html>
```
