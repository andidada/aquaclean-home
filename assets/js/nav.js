/**
 * AquaClean — mobile navigation toggle.
 *
 * style.css used to hide `.nav-links` outright under 768px with no
 * replacement, so phones could not reach About / Why Us / Reviews / Contact
 * at all. This script injects a hamburger button in front of every
 * `.nav-links` and toggles the `.open` class (styled in style.css).
 *
 * The button is created here rather than hand-written into 460+ generated
 * pages so the markup for every language stays in sync.
 */
(function () {
  'use strict';

  function init() {
    var lists = document.querySelectorAll('.nav-links');
    Array.prototype.forEach.call(lists, function (list, i) {
      if (!list.id) list.id = 'navLinks' + (i + 1);
      // 幂等：脚本被重复引入时不要插出两个按钮
      if (list.parentNode.querySelector('.nav-toggle')) return;

      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'nav-toggle';
      btn.setAttribute('aria-label', 'Open menu');
      btn.setAttribute('aria-expanded', 'false');
      btn.setAttribute('aria-controls', list.id);
      btn.innerHTML = '<span aria-hidden="true">&#9776;</span>';
      list.parentNode.insertBefore(btn, list);

      function setOpen(open) {
        list.classList.toggle('open', open);
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        btn.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
      }

      btn.addEventListener('click', function () {
        setOpen(!list.classList.contains('open'));
      });

      // 点菜单里的链接后收起
      list.addEventListener('click', function (e) {
        var a = e.target && e.target.closest ? e.target.closest('a') : null;
        if (a) setOpen(false);
      });

      // 点页面空白处收起
      document.addEventListener('click', function (e) {
        if (!list.classList.contains('open')) return;
        if (list.contains(e.target) || btn.contains(e.target)) return;
        setOpen(false);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
