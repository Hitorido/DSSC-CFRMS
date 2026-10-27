(function () {
  'use strict';

  window.createReservationCalendar = function (root, input, label) {
    var heading = root.querySelector('[data-calendar-month]');
    var days = root.querySelector('[data-calendar-days]');
    var previous = root.querySelector('[data-calendar-previous]');
    var next = root.querySelector('[data-calendar-next]');
    var todayButton = root.querySelector('[data-calendar-today]');

    function parseDate(value) {
      if (!value) return null;
      var parts = value.split('-').map(Number);
      return new Date(parts[0], parts[1] - 1, parts[2], 12);
    }

    function dateValue(date) {
      return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0') + '-' + String(date.getDate()).padStart(2, '0');
    }

    function monthStart(date) {
      return new Date(date.getFullYear(), date.getMonth(), 1, 12);
    }

    // The server supplies today's date in the campus timezone through min.
    var today = parseDate(input.min) || new Date();
    today.setHours(12, 0, 0, 0);
    var minimumValue = dateValue(today);
    var focusedDate;
    var visibleMonth;

    function render() {
      heading.textContent = visibleMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
      previous.disabled = visibleMonth <= monthStart(today);
      var firstDay = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth(), 1 - visibleMonth.getDay(), 12);
      var fragment = document.createDocumentFragment();

      for (var index = 0; index < 42; index += 1) {
        var date = new Date(firstDay.getFullYear(), firstDay.getMonth(), firstDay.getDate() + index, 12);
        var value = dateValue(date);
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'reservation-date-day';
        button.textContent = date.getDate();
        button.dataset.calendarDate = value;
        button.disabled = value < minimumValue;
        button.tabIndex = value === dateValue(focusedDate) ? 0 : -1;
        button.setAttribute('aria-label', date.toLocaleDateString('en-US', {
          weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
        }));
        button.setAttribute('aria-pressed', String(value === input.value));
        if (date.getMonth() !== visibleMonth.getMonth()) button.classList.add('is-outside-month');
        if (value === minimumValue) {
          button.classList.add('is-today');
          button.setAttribute('aria-current', 'date');
        }
        if (value === input.value) button.classList.add('is-selected');
        fragment.appendChild(button);
      }

      days.replaceChildren(fragment);
    }

    function refresh() {
      var selected = parseDate(input.value);
      focusedDate = selected && selected >= today ? selected : new Date(today);
      visibleMonth = monthStart(focusedDate);
      render();
    }

    function focusDay() {
      var button = days.querySelector('[data-calendar-date="' + dateValue(focusedDate) + '"]');
      if (button) button.focus();
    }

    function moveFocus(date) {
      focusedDate = date < today ? new Date(today) : date;
      visibleMonth = monthStart(focusedDate);
      render();
      focusDay();
    }

    function selectDate(value) {
      if (value < minimumValue) return;
      input.value = value;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function changeMonth(offset) {
      visibleMonth = new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + offset, 1, 12);
      focusedDate = visibleMonth < today ? new Date(today) : new Date(visibleMonth);
      render();
    }

    previous.addEventListener('click', function () { changeMonth(-1); });
    next.addEventListener('click', function () { changeMonth(1); });
    todayButton.addEventListener('click', function () { moveFocus(new Date(today)); });

    days.addEventListener('click', function (event) {
      var button = event.target.closest('[data-calendar-date]');
      if (!button || button.disabled) return;
      selectDate(button.dataset.calendarDate);
    });

    days.addEventListener('keydown', function (event) {
      var button = event.target.closest('[data-calendar-date]');
      if (!button) return;
      var date = parseDate(button.dataset.calendarDate);
      var offset = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[event.key];
      if (offset !== undefined) date.setDate(date.getDate() + offset);
      else if (event.key === 'Home') date.setDate(date.getDate() - date.getDay());
      else if (event.key === 'End') date.setDate(date.getDate() + 6 - date.getDay());
      else if (event.key === 'PageUp' || event.key === 'PageDown') {
        var day = date.getDate();
        date.setDate(1);
        date.setMonth(date.getMonth() + (event.key === 'PageUp' ? -1 : 1));
        var lastDay = new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
        date.setDate(Math.min(day, lastDay));
      } else return;
      event.preventDefault();
      moveFocus(date);
    });

    refresh();
    input.hidden = true;
    label.hidden = true;
    root.hidden = false;
    return { refresh: refresh, focus: focusDay };
  };
}());
