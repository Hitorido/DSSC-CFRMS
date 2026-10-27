(function () {
  'use strict';

  var dialog = document.getElementById('homeFacilityPicker');
  if (!dialog) return;
  var title = document.getElementById('homeFacilityPickerTitle');
  var dateLabel = document.getElementById('homeFacilityPickerDate');
  var search = document.getElementById('homeFacilityPickerSearch');
  var empty = document.getElementById('homeFacilityPickerEmpty');
  var options = Array.from(dialog.querySelectorAll('[data-calendar-booking-url]'));
  var activeTrigger;

  function filterFacilities() {
    var query = search ? search.value.trim().toLocaleLowerCase() : '';
    var visible = 0;
    options.forEach(function (option) {
      option.hidden = !option.dataset.calendarFacilitySearch.toLocaleLowerCase().includes(query);
      if (!option.hidden) visible += 1;
    });
    empty.hidden = visible > 0;
    empty.textContent = options.length ? 'No facilities match your search.' : 'No facilities are currently available for booking.';
  }

  document.querySelectorAll('[data-calendar-booking-date]').forEach(function (trigger) {
    trigger.addEventListener('click', function (event) {
      if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      var value = trigger.dataset.calendarBookingDate;
      if (value < dialog.dataset.minDate) {
        event.preventDefault();
        return;
      }
      if (typeof dialog.showModal !== 'function') return;
      event.preventDefault();
      activeTrigger = trigger;
      dateLabel.dateTime = value;
      dateLabel.textContent = new Date(value + 'T00:00:00').toLocaleDateString(undefined, {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
      });
      options.forEach(function (option) {
        var bookingUrl = new URL(option.dataset.calendarBookingUrl, window.location.href);
        bookingUrl.searchParams.set('date', value);
        option.href = bookingUrl.href;
      });
      if (search) search.value = '';
      filterFacilities();
      dialog.showModal();
      title.focus({ preventScroll: true });
    });
  });

  if (search) search.addEventListener('input', filterFacilities);
  dialog.querySelector('[data-calendar-picker-close]').addEventListener('click', function () { dialog.close(); });
  dialog.addEventListener('close', function () {
    if (activeTrigger && activeTrigger.isConnected) activeTrigger.focus({ preventScroll: true });
  });
  dialog.addEventListener('click', function (event) {
    if (event.target !== dialog) return;
    var bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
  });
}());
