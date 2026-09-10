/* ============================================================
   IAGORA — prototype
   Sidebar partagée (variante 5b) + icônes monochromes + pop-ups.
   Aucune dépendance, aucun serveur : tout fonctionne en file://
   ============================================================ */
(function (w) {
  'use strict';

  /* ---------- Icônes : tracé uniquement, couleur héritée ---------- */
  var ICONS = {
    megaphone: '<path d="M4 10v4a1 1 0 0 0 1 1h2l1.2 4.2a1 1 0 0 0 1 .8h.6a1 1 0 0 0 1-1.2L10 15h1l7 3.5a1 1 0 0 0 1.5-.9V6.4A1 1 0 0 0 18 5.5L11 9H5a1 1 0 0 0-1 1Z"/>',
    pencil: '<path d="M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17v3Z"/><path d="M14.5 7.5 16.5 9.5"/>',
    sparkle: '<path d="M12 3.5 13.6 9 19 10.6 13.6 12.2 12 17.7 10.4 12.2 5 10.6 10.4 9 12 3.5Z"/><path d="M18 16.5l.7 2.1 2.1.7-2.1.7-.7 2.1-.7-2.1-2.1-.7 2.1-.7.7-2.1Z"/>',
    files: '<rect x="7" y="3.5" width="12" height="14" rx="2"/><path d="M15.5 20.5H6.8A1.8 1.8 0 0 1 5 18.7V7"/><path d="M10 8h6M10 11.5h6M10 15h3.5"/>',
    clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5.2l3.2 2"/>',
    calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="2.2"/><path d="M3.5 10h17M8 3.5v3M16 3.5v3"/><path d="M7.5 14h2.2M12 14h2.2M7.5 17.2h2.2M12 17.2h2.2"/>',
    chat: '<path d="M20.5 12.4c0 4-3.8 7.2-8.5 7.2a10 10 0 0 1-2.6-.34L4.5 21l1.3-3.6A6.9 6.9 0 0 1 3.5 12.4c0-4 3.8-7.2 8.5-7.2s8.5 3.2 8.5 7.2Z"/>',
    cap: '<path d="M2.8 9.4 12 5.2l9.2 4.2-9.2 4.2-9.2-4.2Z"/><path d="M6.5 11.2v4.4c0 1.5 2.5 2.8 5.5 2.8s5.5-1.3 5.5-2.8v-4.4"/><path d="M21.2 9.4v5.2"/>',
    video: '<rect x="2.8" y="6" width="12.6" height="12" rx="2.4"/><path d="M15.4 11 21.2 8v8l-5.8-3v-2Z"/>',
    chart: '<path d="M4 20h16"/><path d="M6.5 20V13M11 20V7.5M15.5 20v-4.6M20 20V10.5"/>',
    share: '<circle cx="17.5" cy="6" r="2.6"/><circle cx="6.5" cy="12" r="2.6"/><circle cx="17.5" cy="18" r="2.6"/><path d="M15.2 7.3 8.8 10.7M8.8 13.3l6.4 3.4"/>',
    history: '<path d="M3.8 12a8.2 8.2 0 1 0 2.6-6"/><path d="M3.4 3.6v4h4"/><path d="M12 7.6V12l3 1.8"/>',
    bell: '<path d="M6.2 10.3a5.8 5.8 0 0 1 11.6 0c0 3.4.9 5 1.7 5.9.4.4.1 1.1-.5 1.1H5c-.6 0-.9-.7-.5-1.1.8-.9 1.7-2.5 1.7-5.9Z"/><path d="M10 20.2a2.3 2.3 0 0 0 4 0"/>',
    sliders: '<path d="M4 7.5h10M18.5 7.5h1.5M4 16.5h3M11.5 16.5h8.5"/><circle cx="16" cy="7.5" r="2.2"/><circle cx="9" cy="16.5" r="2.2"/>',
    users: '<circle cx="9.4" cy="8.4" r="3.4"/><path d="M3.5 19.5c0-3.1 2.6-5.2 5.9-5.2s5.9 2.1 5.9 5.2"/><path d="M16.6 5.4a3.2 3.2 0 0 1 0 6.1M17.6 14.6c2.1.5 3.4 2 3.4 4.2"/>',
    gear: '<circle cx="12" cy="12" r="2.9"/><path d="M12 3.5v2.1M12 18.4v2.1M20.5 12h-2.1M5.6 12H3.5M18 6l-1.5 1.5M7.5 16.5 6 18M18 18l-1.5-1.5M7.5 7.5 6 6"/>',
    search: '<circle cx="11" cy="11" r="6.4"/><path d="M15.8 15.8 20.5 20.5"/>',
    chevron: '<path d="M6.5 9.5 12 15l5.5-5.5"/>',
    panelLeft: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.2"/><path d="M10 4.5v15"/>',
    plus: '<path d="M12 5.5v13M5.5 12h13"/>',
    close: '<path d="M6.5 6.5 17.5 17.5M17.5 6.5 6.5 17.5"/>',
    filter: '<path d="M4 6h16l-6.2 7.2v5.3l-3.6 1.8v-7.1L4 6Z"/>',
    download: '<path d="M12 4v10.5M7.8 10.6 12 14.8l4.2-4.2"/><path d="M4.5 18.5h15"/>',
    external: '<path d="M14 5h5v5"/><path d="M19 5l-7.5 7.5"/><path d="M18 14.5v4a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 4 18.5v-11A1.5 1.5 0 0 1 5.5 6h4"/>',
    arrowRight: '<path d="M5 12h13M13 7l5 5-5 5"/>',
    check: '<path d="M5 12.5 10 17.5 19 6.5"/>',
    dots: '<circle cx="5.5" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="18.5" cy="12" r="1.4" fill="currentColor" stroke="none"/>',
    image: '<rect x="3.5" y="5" width="17" height="14" rx="2.2"/><circle cx="8.8" cy="10" r="1.6"/><path d="M4 16.5 9.5 12l4 3.4 3-2.4 4 3.5"/>',
    send: '<path d="M20.5 3.5 3.5 10.2l6.8 2.8 2.8 6.8 7.4-16.3Z"/><path d="M10.3 13 20.5 3.5"/>',
    grid: '<rect x="4" y="4" width="7" height="7" rx="1.6"/><rect x="13" y="4" width="7" height="7" rx="1.6"/><rect x="4" y="13" width="7" height="7" rx="1.6"/><rect x="13" y="13" width="7" height="7" rx="1.6"/>',
    columns: '<rect x="3.5" y="4.5" width="5" height="15" rx="1.6"/><rect x="9.5" y="4.5" width="5" height="15" rx="1.6"/><rect x="15.5" y="4.5" width="5" height="15" rx="1.6"/>',
    warn: '<path d="M12 4.5 21 19.5H3L12 4.5Z"/><path d="M12 10v4M12 16.6v.1"/>'
  };

  function icon(name, cls) {
    var p = ICONS[name] || '';
    return '<svg class="ico ' + (cls || '') + '" viewBox="0 0 24 24" aria-hidden="true">' + p + '</svg>';
  }

  /* ---------- Logos de réseaux : monochromes, même famille graphique ---------- */
  function netChip(inner) {
    return '<rect x="2" y="2" width="20" height="20" rx="5.5" fill="none" stroke="currentColor" stroke-width="1.5"/>' + inner;
  }
  var NETS = {
    facebook: netChip('<path d="M14.6 8.2h-1.3c-.5 0-.8.3-.8.9v1.6h2.1l-.3 2.2h-1.8v5.3h-2.2v-5.3H8.8v-2.2h1.5V8.8c0-1.7 1-2.7 2.7-2.7h1.6v2.1Z" fill="currentColor" stroke="none"/>'),
    instagram: '<rect x="2" y="2" width="20" height="20" rx="5.5" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="12" cy="12" r="3.6" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="17.1" cy="6.9" r="1.05" fill="currentColor" stroke="none"/>',
    linkedin: netChip('<rect x="6.2" y="10" width="2.2" height="7.8" fill="currentColor" stroke="none"/><circle cx="7.3" cy="7.1" r="1.3" fill="currentColor" stroke="none"/><path d="M10.6 17.8V10h2.1v1.1c.5-.8 1.3-1.3 2.4-1.3 1.8 0 2.8 1.1 2.8 3.2v4.8h-2.2v-4.3c0-1.1-.4-1.8-1.3-1.8s-1.5.7-1.5 1.8v4.3h-2.3Z" fill="currentColor" stroke="none"/>'),
    youtube: netChip('<path d="M9.8 8.4 16.6 12l-6.8 3.6V8.4Z" fill="currentColor" stroke="none"/>'),
    tiktok: netChip('<path d="M13.4 6.1h1.9c.2 1.5 1.1 2.5 2.6 2.7v1.9c-1-.05-1.9-.35-2.6-.9v4c0 2.2-1.6 3.7-3.6 3.7a3.6 3.6 0 0 1 0-7.2c.2 0 .4 0 .6.05v2a1.7 1.7 0 1 0 1.1 1.6V6.1Z" fill="currentColor" stroke="none"/>')
  };

  function netLogo(name, cls) {
    return '<svg class="logo-net ' + (cls || '') + '" viewBox="0 0 24 24" role="img" aria-label="' +
      name.charAt(0).toUpperCase() + name.slice(1) + '">' + (NETS[name] || '') + '</svg>';
  }

  /* ---------- Structure de navigation ----------
     « Tableau de bord » et « Inscriptions » retirés : aucune maquette
     ne leur correspond dans l'export v2.1.                            */
  var NAV = [
    { type: 'group', key: 'publier', label: 'Publier', icon: 'megaphone', items: [
      { key: 'creer',    label: 'Créer une publication',    icon: 'pencil',  href: 'creer-publication.html' },
      { key: 'generer',  label: 'Générer une publication',  icon: 'sparkle', href: 'generer-publication.html' },
      { key: 'publications', label: 'Publications',         icon: 'files',   href: 'publications.html', count: '128' }
    ]},
    { type: 'group', key: 'programmer', label: 'Programmer', icon: 'clock', items: [
      { key: 'calendrier', label: 'Calendrier', icon: 'calendar', href: 'calendrier.html', count: '12' }
    ]},
    { type: 'group', key: 'interagir', label: 'Interagir', icon: 'chat', items: [
      { key: 'messages', label: 'Messages unifiés', icon: 'chat', href: 'messages.html', badge: '7' }
    ]},
    { type: 'group', key: 'evenements', label: 'Événements', icon: 'cap', items: [
      { key: 'webinaires', label: 'Webinaires', icon: 'video', href: 'webinaires.html', count: '2' }
    ]},
    { type: 'group', key: 'mesurer', label: 'Mesurer', icon: 'chart', items: [
      { key: 'reseaux',    label: 'Gestion des réseaux',     icon: 'share',   href: 'reseaux.html', count: '4' },
      { key: 'historique', label: 'Historique des activités', icon: 'history', href: 'historique.html' }
    ]},
    { type: 'item', key: 'notifications', label: 'Notifications', icon: 'bell', href: 'notifications.html', badge: '3' },
    { type: 'group', key: 'administrer', label: 'Administrer', icon: 'sliders', items: [
      { key: 'utilisateurs', label: 'Utilisateurs', icon: 'users', href: 'utilisateurs.html', count: '14' },
      { key: 'parametres',   label: 'Paramètres',   icon: 'gear',  href: 'parametres.html' }
    ]}
  ];

  function itemHTML(it, active) {
    var tail = it.badge ? '<span class="sb-badge">' + it.badge + '</span>'
             : it.count ? '<span class="sb-count">' + it.count + '</span>' : '';
    return '<a class="sb-item' + (active ? ' is-active' : '') + '" href="' + it.href +
      '" data-key="' + it.key + '" title="' + it.label + '">' +
      icon(it.icon) + '<span class="sb-label">' + it.label + '</span>' + tail + '</a>';
  }

  function sidebarHTML(current) {
    var out = '';
    out += '<div class="sb-head">' +
      '<a class="sb-brand" href="publications.html">' +
        '<span class="sb-mark">IA</span><span class="sb-name">IAGORA</span>' +
      '</a>' +
      '<button class="sb-toggle" type="button" data-act="rail" title="Replier la navigation" aria-label="Replier la navigation">' +
        icon('panelLeft', 'ico-sm') +
      '</button>' +
    '</div>';

    out += '<button class="sb-search" type="button" data-act="search">' +
      '<span class="ico-wrap">' + icon('search', 'ico-sm') + '</span>' +
      '<span>Rechercher une page</span><span class="k">Ctrl K</span>' +
    '</button>';

    NAV.forEach(function (n) {
      if (n.type === 'item') {
        out += itemHTML(n, current === n.key);
        return;
      }
      var hasActive = n.items.some(function (i) { return i.key === current; });
      var closed = !hasActive && w.localStorage.getItem('iagora.grp.' + n.key) === 'closed';
      out += '<div class="sb-group' + (closed ? ' is-closed' : '') + '" data-grp="' + n.key + '">' +
        '<button class="sb-gh" type="button">' + icon(n.icon, 'ico-sm') +
          '<span>' + n.label + '</span>' + icon('chevron', 'chev') +
        '</button>' +
        '<div class="sb-sub">' + n.items.map(function (i) {
          return itemHTML(i, current === i.key);
        }).join('') + '</div>' +
      '</div>';
    });

    out += '<div class="sb-foot"><button class="sb-user" type="button">' +
      '<span class="sb-av">SL</span>' +
      '<span class="sb-who"><b>Sarah Lemoine</b><span>Datum Academy · admin</span></span>' +
      icon('chevron', 'ico-sm') +
    '</button></div>';

    return out;
  }

  function mountSidebar() {
    var host = document.querySelector('.sidebar');
    if (!host) return;
    host.innerHTML = sidebarHTML(document.body.getAttribute('data-page') || '');
    if (w.localStorage.getItem('iagora.rail') === '1') host.classList.add('is-rail');

    host.addEventListener('click', function (e) {
      var rail = e.target.closest('[data-act="rail"]');
      if (rail) {
        var on = !host.classList.contains('is-rail');
        host.classList.toggle('is-rail', on);
        w.localStorage.setItem('iagora.rail', on ? '1' : '0');
        return;
      }
      var gh = e.target.closest('.sb-gh');
      if (gh) {
        var grp = gh.parentElement;
        var closed = grp.classList.toggle('is-closed');
        w.localStorage.setItem('iagora.grp.' + grp.getAttribute('data-grp'), closed ? 'closed' : 'open');
      }
    });
  }

  /* ---------- Pop-ups ---------- */
  function openModal(id) {
    var m = document.getElementById(id);
    if (m) { m.hidden = false; document.body.style.overflow = 'hidden'; }
  }
  function closeModal(el) {
    var m = typeof el === 'string' ? document.getElementById(el) : el;
    if (m) { m.hidden = true; document.body.style.overflow = ''; }
  }

  document.addEventListener('click', function (e) {
    var op = e.target.closest('[data-modal-open]');
    if (op) { e.preventDefault(); openModal(op.getAttribute('data-modal-open')); return; }
    var cl = e.target.closest('[data-modal-close]');
    if (cl) { e.preventDefault(); closeModal(cl.closest('.modal-back')); return; }
    if (e.target.classList && e.target.classList.contains('modal-back')) closeModal(e.target);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    Array.prototype.forEach.call(document.querySelectorAll('.modal-back:not([hidden])'), closeModal);
  });

  /* ---------- Petits comportements de prototype ---------- */
  document.addEventListener('click', function (e) {
    // groupes de filtres : un seul actif à la fois
    var chip = e.target.closest('[data-chipgroup] .chip');
    if (chip) {
      var grp = chip.closest('[data-chipgroup]');
      Array.prototype.forEach.call(grp.querySelectorAll('.chip'), function (c) { c.classList.remove('is-on'); });
      chip.classList.add('is-on');
      return;
    }
    // lignes de tableau sélectionnables
    var row = e.target.closest('[data-selectable] tbody tr');
    if (row) {
      var tb = row.closest('tbody');
      Array.prototype.forEach.call(tb.querySelectorAll('tr'), function (r) { r.classList.remove('is-sel'); });
      row.classList.add('is-sel');
    }
  });

  document.addEventListener('DOMContentLoaded', function () {
    mountSidebar();
    // rendu différé des icônes déclarées en HTML : <i data-ico="bell"></i>
    Array.prototype.forEach.call(document.querySelectorAll('[data-ico]'), function (el) {
      el.outerHTML = icon(el.getAttribute('data-ico'), el.className);
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-net]'), function (el) {
      el.outerHTML = netLogo(el.getAttribute('data-net'), el.className);
    });
  });

  w.IAGORA = { icon: icon, netLogo: netLogo, openModal: openModal, closeModal: closeModal, NAV: NAV };
})(window);
