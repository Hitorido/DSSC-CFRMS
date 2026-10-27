(function () {
  'use strict';

  window.createReservationCalendar = function (root, input, label) {
    var heading = root.querySelector('[data-calendar-month]');
    var days = root.querySelector('[data-calendar-days]');
    var previous = root.querySelector('[data-calendar-previous]');
    var next = root.querySelector('[data-calendar-next]');
    var todayButton = root.querySelector('[data-calendar-today]');

    // Cache of fetched day data: key = 'YYYY-MM-DD', value = {occupancy, reservations, is_available}
    var dayDataCache = {};
    var rendering = false;

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

    function getFacilityId() {
      var widget = document.querySelector('[data-facility-id]');
      return widget ? widget.dataset.facilityId : null;
    }

    function formatTime(timeStr) {
      if (!timeStr) return '';
      var parts = timeStr.split(':');
      var h = parseInt(parts[0]);
      var m = parts[1];
      var ampm = h >= 12 ? 'PM' : 'AM';
      var display = h % 12 || 12;
      return display + ':' + m + ' ' + ampm;
    }

    function getOccupancyClass(occupancy) {
      if (occupancy === null || occupancy === undefined) return '';
      if (occupancy <= 33) return 'day-available-low';
      if (occupancy <= 66) return 'day-available-medium';
      return 'day-available-high';
    }

    async function fetchMonthData(year, month, facilityId) {
      if (!facilityId) return;
      var daysInMonth = new Date(year, month + 1, 0).getDate();
      var fetches = [];
      for (var d = 1; d <= daysInMonth; d++) {
        var ds = year + '-' + String(month + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
        if (!dayDataCache[ds]) fetches.push(ds);
      }
      await Promise.all(fetches.map(async function(ds) {
        try {
          var response = await fetch('/facilities/' + facilityId + '/calendar-api/' + ds + '/');
          if (response.ok) dayDataCache[ds] = await response.json();
        } catch (e) { /* silently ignore */ }
      }));
    }

    // The server supplies today's date through the input's min attribute.
    var today = parseDate(input.min) || new Date();
    today.setHours(12, 0, 0, 0);
    var minimumValue = dateValue(today);
    var focusedDate;
    var visibleMonth;

    async function render() {
      if (rendering) return;
      rendering = true;
      try {
        var facilityId = getFacilityId();
        if (facilityId) {
          await fetchMonthData(visibleMonth.getFullYear(), visibleMonth.getMonth(), facilityId);
        }

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

          // Color coding + tooltip from facility calendar API
          if (facilityId && dayDataCache[value] && !button.disabled && date.getMonth() === visibleMonth.getMonth()) {
            var dayData = dayDataCache[value];
            var colorClass = getOccupancyClass(dayData.occupancy);
            if (colorClass) button.classList.add(colorClass);

            // Hover tooltip
            var tooltip = document.createElement('div');
            tooltip.className = 'calendar-booking-tooltip';
            var html = '<div class="tooltip-occupancy">' + (dayData.occupancy || 0) + '% occupied</div>';
            if (dayData.reservations && dayData.reservations.length > 0) {
              html += '<div class="tooltip-section"><div class="tooltip-section-title">Reservations (' + dayData.reservations.length + ')</div>';
              dayData.reservations.forEach(function(res) {
                html += '<div class="tooltip-item"><strong>' + formatTime(res.start_time) + ' &ndash; ' + formatTime(res.end_time) + '</strong><br>' + (res.purpose || '') + '</div>';
              });
              html += '</div>';
            } else {
              html += '<div class="tooltip-section"><em>No bookings yet</em></div>';
            }
            if (dayData.maintenance && dayData.maintenance.length > 0) {
              html += '<div class="tooltip-section"><div class="tooltip-section-title">Maintenance</div>';
              dayData.maintenance.forEach(function(m) {
                html += '<div class="tooltip-item"><strong>' + formatTime(m.start_time) + ' &ndash; ' + formatTime(m.end_time) + '</strong><br>' + (m.title || '') + '</div>';
              });
              html += '</div>';
            }
            tooltip.innerHTML = html;
            button.style.position = 'relative';
            button.appendChild(tooltip);
          }

          fragment.appendChild(button);
        }
        days.replaceChildren(fragment);
      } finally {
        rendering = false;
      }
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
      setTimeout(focusDay, 50);
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

    // Re-render when the facility select changes so colors update for new facility
    document.addEventListener('change', function(e) {
      if (e.target && e.target.name && e.target.name.includes('facility')) {
        dayDataCache = {};
        render();
      }
    });

    refresh();
    input.hidden = true;
    label.hidden = true;
    root.hidden = false;
    return { refresh: refresh, focus: focusDay };
  };
}());
