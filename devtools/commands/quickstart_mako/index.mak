<%inherit file="local:templates.master"/>

<%def name="title()">
  Welcome to TurboGears 2.2, standing on the shoulders of giants, since 2007
</%def>

  <div class="row">
    <div class="span8 hidden-phone hidden-tablet">
      <div class="hero-unit">
        <h1>Welcome to TurboGears 2.2</h1>
        <p>If you see this page it means your installation was successful!</p>
        <p>TurboGears 2 is rapid web application development toolkit designed to make your life easier.</p>
        <p>
          <a class="btn btn-primary btn-large" href="http://www.turbogears.org" target="_blank">
            ${h.icon('book', True)} Learn more
          </a>
        </p>
      </div>
    </div>
    <div class="span4">
      <a class="btn btn-small" href="http://www.turbogears.org/2.2/docs/">${h.icon('book')} TG2 Documents</a> <span class="label label-success">new</span> Read the Getting Started section<br/>
        <br/>
      <a class="btn btn-small" href="http://www.turbogears.org/book/">${h.icon('book')} TG2 Book</a> Work in progress TurboGears2 book<br/>
        <br/>
      <a class="btn btn-small" href="http://groups.google.com/group/turbogears">${h.icon('comment')} Join the Mail List</a> for general TG use/topics
    </div>
  </div>

  <div class="row">
    <div class="span4">
      <h3>Code your data model</h3>
      <p> Design your data <code>model</code>, Create the database, and Add some bootstrap data.</p>
    </div>

    <div class="span4">
      <h3>Design your URL architecture</h3>
      <p> Decide your URLs, Program your <code>controller</code> methods, Design your
        <code>templates</code>, and place some static files (CSS and/or Javascript). </p>
    </div>

    <div class="span4">
      <h3>Distribute your app</h3>
      <p> Test your source, Generate project documents, Build a distribution.</p>
    </div>
  </div>

  <div class="notice"> Thank you for choosing TurboGears.</div>
