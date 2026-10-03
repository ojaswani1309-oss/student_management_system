/* Student Management System - small vanilla JavaScript helpers */
document.addEventListener('DOMContentLoaded', function () {
  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  /* ---- Mobile sidebar ---- */
  var sidebar = $('#sidebar'), backdrop = $('#sidebarBackdrop'), toggle = $('#menuToggle');
  function setSidebar(open) {
    if (!sidebar) return;
    sidebar.classList.toggle('open', open);
    backdrop.classList.toggle('open', open);
  }
  if (toggle) toggle.addEventListener('click', function () { setSidebar(!sidebar.classList.contains('open')); });
  if (backdrop) backdrop.addEventListener('click', function () { setSidebar(false); });

  /* ---- Alerts: close button + auto-hide after 6 seconds ---- */
  $$('.alert').forEach(function (alert) {
    var btn = $('.alert-close', alert);
    if (btn) btn.addEventListener('click', function () { alert.remove(); });
    setTimeout(function () { if (alert.parentNode) alert.remove(); }, 6000);
  });

  /* ---- Delete confirmation modal ---- */
  var modal = $('#deleteModal');
  if (modal) {
    var form = $('#deleteForm'), message = $('#deleteMessage');
    $$('[data-delete-url]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        form.action = btn.getAttribute('data-delete-url');
        message.textContent = 'Are you sure you want to delete ' + btn.getAttribute('data-delete-name') + '? This cannot be undone.';
        modal.classList.add('open');
      });
    });
    $$('[data-close-modal]').forEach(function (b) { b.addEventListener('click', function () { modal.classList.remove('open'); }); });
    modal.addEventListener('click', function (e) { if (e.target === modal) modal.classList.remove('open'); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') modal.classList.remove('open'); });
  }

  /* ---- Filters: submit the form automatically when a dropdown changes ---- */
  $$('select[data-autosubmit]').forEach(function (sel) {
    sel.addEventListener('change', function () { sel.form.submit(); });
  });

  /* ---- Dependent dropdowns, e.g. data-filter="id_course:course,id_semester:semester"
         shows only the options whose data-course / data-semester match the chosen parents ---- */
  $$('select[data-filter]').forEach(function (child) {
    var rules = child.getAttribute('data-filter').split(',').map(function (r) {
      var parts = r.split(':');
      return { parent: document.getElementById(parts[0]), key: parts[1] };
    }).filter(function (r) { return r.parent; });

    function apply() {
      Array.prototype.forEach.call(child.options, function (opt) {
        if (!opt.value) return;
        var visible = rules.every(function (r) {
          return !r.parent.value || !opt.dataset[r.key] || opt.dataset[r.key] === r.parent.value;
        });
        opt.hidden = !visible;
        opt.disabled = !visible;
      });
      var chosen = child.options[child.selectedIndex];
      if (chosen && chosen.value && chosen.disabled) child.value = '';
    }
    rules.forEach(function (r) { r.parent.addEventListener('change', apply); });
    apply();
  });

  /* Student form: filter the Course dropdown by the chosen Department */
  var dept = document.getElementById('id_department'), course = document.getElementById('id_course');
  if (dept && course && !course.hasAttribute('data-filter') && course.querySelector('option[data-department]')) {
    course.setAttribute('data-filter', 'id_department:department');
    var applyCourse = function () {
      Array.prototype.forEach.call(course.options, function (opt) {
        if (!opt.value) return;
        var ok = !dept.value || opt.getAttribute('data-department') === dept.value;
        opt.hidden = !ok; opt.disabled = !ok;
      });
      var cur = course.options[course.selectedIndex];
      if (cur && cur.value && cur.disabled) course.value = '';
    };
    dept.addEventListener('change', applyCourse);
    applyCourse();
  }

  /* ---- Attendance: "All Present" / "All Absent" buttons ---- */
  $$('[data-mark-all]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var value = btn.getAttribute('data-mark-all');
      $$('input[type=radio][value=' + value + ']').forEach(function (r) { r.checked = true; });
    });
  });

  /* ---- Client-side validation (the server validates again) ---- */
  function showError(input, text) {
    clearError(input);
    input.classList.add('has-error');
    var div = document.createElement('div');
    div.className = 'field-error js-error';
    div.textContent = text;
    input.parentNode.appendChild(div);
  }
  function clearError(input) {
    input.classList.remove('has-error');
    var old = input.parentNode.querySelector('.js-error');
    if (old) old.remove();
  }
  $$('form[novalidate]').forEach(function (f) {
    f.addEventListener('submit', function (e) {
      var ok = true;
      $$('input, select, textarea', f).forEach(function (input) {
        if (input.type === 'hidden' || input.type === 'file') return;
        clearError(input);
        var value = input.value.trim();
        if (input.hasAttribute('required') && !value) { showError(input, 'This field is required.'); ok = false; return; }
        if (!value) return;
        if (input.type === 'email' && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value)) { showError(input, 'Enter a valid email address.'); ok = false; }
        if (input.getAttribute('pattern') && !new RegExp('^(?:' + input.getAttribute('pattern') + ')$').test(value)) { showError(input, 'Enter a valid phone number (10-15 digits).'); ok = false; }
        if (input.type === 'number') {
          var n = Number(value), min = input.getAttribute('min'), max = input.getAttribute('max');
          if ((min !== null && n < Number(min)) || (max !== null && n > Number(max))) {
            showError(input, 'Value must be between ' + min + ' and ' + max + '.'); ok = false;
          }
        }
      });
      if (!ok) { e.preventDefault(); var first = $('.has-error', f); if (first) first.focus(); }
    });
  });
});
