const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

class Field {
  constructor({name='desired_date', type='text', disabled=false, readOnly=false, ignored=false} = {}) {
    this.name = name; this.type = type; this.disabled = disabled; this.readOnly = readOnly;
    this.dataset = ignored ? {analyticsIgnore: ''} : {};
  }
  matches(selector) { return selector === 'input, select, textarea'; }
  closest(selector) { return null; }
}
class Form {
  constructor(dataset = {}) { this.dataset = dataset; this.listeners = {}; }
  addEventListener(type, cb) { (this.listeners[type] ||= []).push(cb); }
  dispatch(type, target, isTrusted = true) { (this.listeners[type] || []).forEach(cb => cb({target, isTrusted})); }
}
function load() {
  const forms = [];
  const context = {
    window: {},
    document: { addEventListener() {}, querySelectorAll(sel) { return sel === 'form[data-analytics-booking-form]' ? forms : []; } },
    console,
  };
  context.window.localStorage = { getItem: () => 'accepted' };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync('static/js/booking-form-start-tracker.js', 'utf8'), context);
  return context;
}
function enabledDataset() {
  return {analyticsEnabled:'true', analyticsServiceSlug:'tresses-plaquees', analyticsServiceCategory:'tresses', analyticsStylistSelected:'true', analyticsBookingFlowVersion:'provider_standard_v1'};
}

{
  const ctx = load(); let meta = 0, plausible = 0, payload;
  const form = new Form(enabledDataset());
  new ctx.window.BookingFormStartTracker(form, [{trackBookingFormStarted:p=>{meta++; payload=p;}}, {trackBookingFormStarted:()=>plausible++}]);
  form.dispatch('input', new Field());
  form.dispatch('change', new Field({name:'client_name'}));
  assert.equal(meta, 1); assert.equal(plausible, 1);
  assert.deepEqual(payload, {service_slug:'tresses-plaquees', service_category:'tresses', stylist_selected:true, booking_flow_version:'provider_standard_v1'});
}
{
  const ctx = load(); let calls = 0; const form = new Form(enabledDataset());
  new ctx.window.BookingFormStartTracker(form, [{trackBookingFormStarted:()=>calls++}]);
  form.dispatch('change', new Field(), false); // automatic population
  form.dispatch('focus', new Field());
  form.dispatch('change', new Field({type:'hidden'}));
  form.dispatch('change', new Field({disabled:true}));
  form.dispatch('change', new Field({readOnly:true}));
  form.dispatch('change', new Field({ignored:true}));
  assert.equal(calls, 0);
}
{
  const ctx = load(); let calls = 0; const form = new Form({...enabledDataset(), analyticsEnabled:'false'});
  new ctx.window.BookingFormStartTracker(form, [{trackBookingFormStarted:()=>calls++}]);
  form.dispatch('change', new Field());
  assert.equal(calls, 0);
}
{
  const ctx = load(); let calls = 0; ctx.window.localStorage.getItem = () => 'rejected'; const form = new Form(enabledDataset());
  new ctx.window.BookingFormStartTracker(form, [{trackBookingFormStarted:()=>calls++}]);
  form.dispatch('change', new Field());
  assert.equal(calls, 0);
}
{
  const ctx = load(); let ok = 0; const form = new Form(enabledDataset());
  new ctx.window.BookingFormStartTracker(form, [{trackBookingFormStarted:()=>{throw new Error('blocked')}}, {trackBookingFormStarted:()=>ok++}]);
  form.dispatch('change', new Field({name:'client_email'}));
  assert.equal(ok, 1);
}
{
  const ctx = load(); let meta = [], plausible = [];
  ctx.window.fbq = (...args) => meta.push(args);
  ctx.window.plausible = (...args) => plausible.push(args);
  vm.runInContext("window.chateauRoseMetaAnalytics={trackBookingFormStarted:function(payload){try{if(typeof window.fbq==='function'){window.fbq('trackCustom','BookingFormStarted',payload||{});}}catch(e){}}}; window.chateauRosePlausibleAnalytics={trackBookingFormStarted:function(payload){try{if(typeof window.plausible==='function'){window.plausible('BookingFormStarted',{props:payload||{}});}}catch(e){}}};", ctx);
  ctx.window.chateauRoseMetaAnalytics.trackBookingFormStarted({client_name:'Awa', service_slug:'tresses'});
  ctx.window.chateauRosePlausibleAnalytics.trackBookingFormStarted({client_name:'Awa', service_slug:'tresses'});
  assert.equal(meta[0][0], 'trackCustom'); assert.equal(meta[0][1], 'BookingFormStarted');
  assert.equal(plausible[0][0], 'BookingFormStarted');
}
{
  const ctx = load(); let calls = 0, stored = {};
  ctx.window.sessionStorage = { getItem: (key) => stored[key] || null, setItem: (key, value) => { stored[key] = value; } };
  const form = new Form(enabledDataset());
  form.__bookingFormStartTracker = new ctx.window.BookingFormStartTracker(form, [{trackInitiateCheckout:()=>calls++}]);
  ctx.window.chateauRoseBookingAnalytics.trackInitiateCheckout(form);
  ctx.window.chateauRoseBookingAnalytics.trackInitiateCheckout(form);
  assert.equal(calls, 1);
}
{
  const ctx = load(); let calls = 0, stored = {};
  ctx.window.sessionStorage = { getItem: (key) => stored[key] || null, setItem: (key, value) => { stored[key] = value; } };
  ctx.window.localStorage.getItem = () => 'rejected';
  const form = new Form(enabledDataset());
  form.__bookingFormStartTracker = new ctx.window.BookingFormStartTracker(form, [{trackInitiateCheckout:()=>calls++}]);
  ctx.window.chateauRoseBookingAnalytics.trackInitiateCheckout(form);
  assert.equal(calls, 0);
}
{
  const ctx = load(); let meta = [];
  ctx.window.fbq = (...args) => meta.push(args);
  vm.runInContext("window.chateauRoseMetaAnalytics={trackInitiateCheckout:function(payload){try{if(typeof window.fbq==='function'){window.fbq('track','InitiateCheckout',payload||{});}}catch(e){}}};", ctx);
  ctx.window.chateauRoseMetaAnalytics.trackInitiateCheckout({service_slug:'tresses'});
  assert.equal(meta[0][0], 'track'); assert.equal(meta[0][1], 'InitiateCheckout');
}

console.log('booking-form-start-tracker tests passed');
