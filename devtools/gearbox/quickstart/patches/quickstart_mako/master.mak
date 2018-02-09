<!DOCTYPE html>
<html>
<head>
    ${self.meta()}
    <title>${self.title()}</title>
    <link rel="stylesheet" type="text/css" media="screen" href="${tg.url('/css/bootstrap.min.css')}" />
    <link rel="stylesheet" type="text/css" media="screen" href="${tg.url('/css/style.css')}" />
    ${self.head_content()}
</head>
<body class="${self.body_class()}">
    ${self.main_menu()}
  <div class="container">
    ${self.content_wrapper()}
  </div>
    ${self.footer()}
  <script src="http://code.jquery.com/jquery.js"></script>
  <script src="${tg.url('/javascript/bootstrap.min.js')}"></script>
</body>

<%def name="content_wrapper()">
  <%
    flash=tg.flash_obj.render('flash', use_js=False)
  %>
  % if flash:
      <div class="row">
        <div class="col-md-8 col-md-offset-2">
              ${flash | n}
        </div>
      </div>
  % endif
  ${self.body()}
</%def>

<%def name="body_class()"></%def>
<%def name="meta()">
  <meta charset="${response.charset}" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</%def>
<%def name="head_content()"></%def>

<%def name="title()">  </%def>

<%def name="footer()">
  <footer class="footer hidden-xs hidden-sm">
    <a class="pull-right" href="http://www.turbogears.org"><img style="vertical-align:middle;" src="${tg.url('/img/under_the_hood_blue.png')}" alt="TurboGears 2" /></a>
    <p>Copyright &copy; ${getattr(tmpl_context, 'project_name', 'TurboGears2')} ${h.current_year()}</p>
  </footer>
</%def>

<%def name="main_menu()">
  <!-- Navbar -->
  <nav class="navbar navbar-default">
    <div class="navbar-header">
      <button type="button" class="navbar-toggle" data-toggle="collapse" data-target="#navbar-content">
        <span class="sr-only">Toggle navigation</span>
        <span class="icon-bar"></span>
        <span class="icon-bar"></span>
        <span class="icon-bar"></span>
      </button>
      <a class="navbar-brand" href="${tg.url('/')}">
        <img src="${tg.url('/img/turbogears_logo.png')}" height="20" alt="TurboGears 2"/>
        ${getattr(tmpl_context, 'project_name', 'turbogears2')}
      </a>
    </div>

    <div class="collapse navbar-collapse" id="navbar-content">
      <ul class="nav navbar-nav">
        <li class="${('', 'active')[page=='index']}"><a href="${tg.url('/')}">Welcome</a></li>
        <li class="${('', 'active')[page=='about']}"><a href="${tg.url('/about')}">About</a></li>
        <li class="${('', 'active')[page=='data']}"><a href="${tg.url('/data')}">Serving Data</a></li>
        <li class="${('', 'active')[page=='environ']}"><a href="${tg.url('/environ')}">WSGI Environment</a></li>
      </ul>

    % if tg.auth_stack_enabled:
      <ul class="nav navbar-nav navbar-right">
      % if not request.identity:
        <li><a href="${tg.url('/login')}">Login</a></li>
      % else:
        <li><a href="${tg.url('/logout_handler')}">Logout</a></li>
        <li><a href="${tg.url('/admin')}">Admin</a></li>
      % endif
      </ul>
    % endif
    </div>
  </nav>
</%def>

</html>
