<!DOCTYPE html>
<html>
<head>
    ${self.meta()}
    <title>${self.title()}</title>
    <link rel="stylesheet" type="text/css" media="screen" href="${tg.url('/css/bootstrap.min.css')}" />
    <link rel="stylesheet" type="text/css" media="screen" href="${tg.url('/css/bootstrap-responsive.min.css')}" />
    <link rel="stylesheet" type="text/css" media="screen" href="${tg.url('/css/style.css')}" />
</head>
<body class="${self.body_class()}">
  <div class="container">
    ${self.main_menu()}
    ${self.content_wrapper()}
    ${self.footer()}
  </div>
</body>

<%def name="content_wrapper()">
  <%
    flash=tg.flash_obj.render('flash', use_js=False)
  %>
  % if flash:
    <div class="row"><div class="span8 offset2">
      ${flash | n}
    </div></div>
  % endif
  ${self.body()}
</%def>

<%def name="body_class()"></%def>
<%def name="meta()">
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</%def>

<%def name="title()">  </%def>

<%def name="footer()">
  <footer class="footer hidden-tablet hidden-phone">
    <a class="pull-right" href="http://www.turbogears.org/2.2/"><img style="vertical-align:middle;" src="${tg.url('/images/under_the_hood_blue.png')}" alt="TurboGears 2" /></a>
    <p>Copyright &copy; ${getattr(tmpl_context, 'project_name', 'TurboGears2')} ${h.current_year()}</p>
  </footer>
</%def>

<%def name="main_menu()">
  <div class="navbar">
    <div class="navbar-inner">
      <div class="container">
        <a class="brand" href="#"><img src="${tg.url('/images/turbogears_logo.png')}" alt="TurboGears 2"/> ${getattr(tmpl_context, 'project_name', 'turbogears2')}</a>
        <ul class="nav">
          <li class="${('', 'active')[page=='index']}"><a href="${tg.url('/')}">Welcome</a></li>
          <li class="${('', 'active')[page=='about']}"><a href="${tg.url('/about')}">About</a></li>
          <li class="${('', 'active')[page=='data']}"><a href="${tg.url('/data')}">Serving Data</a></li>
          <li class="${('', 'active')[page=='environ']}"><a href="${tg.url('/environ')}">WSGI Environment</a></li>
        </ul>

        % if tg.auth_stack_enabled:
          <ul class="nav pull-right">
            % if not request.identity:
              <li><a href="${tg.url('/login')}">Login</a></li>
            % else:
              <li><a href="${tg.url('/logout_handler')}">Logout</a></li>
              <li><a href="${tg.url('/admin')}">Admin</a></li>
            % endif
          </ul>
        % endif
      </div>
    </div>
  </div>
</%def>

</html>
