'use strict';

const ga = Process.getModuleByName('GameAssembly.dll');
const EXPECTED_CALLER_RVA = ptr('0x389a8b7');
const MPD_TYPE_INDEX = 64704;
const MPP_TYPE_INDEX = 64729;
const api = (name, ret, args) => new NativeFunction(ga.getExportByName(name), ret, args);
const domainGet = api('il2cpp_domain_get', 'pointer', []);
const attachThread = api('il2cpp_thread_attach', 'pointer', ['pointer']);
const detachThread = api('il2cpp_thread_detach', 'void', ['pointer']);
const classFromType = api('il2cpp_class_from_type', 'pointer', ['pointer']);
const methodFromName = api('il2cpp_class_get_method_from_name', 'pointer', ['pointer', 'pointer', 'int']);

function resolveMethod(typeIndex, methodName, argc) {
  const types = ga.base.add(0x6f0c700).add(0x38).readPointer();
  const token = attachThread(domainGet());
  try {
    const type = types.add(typeIndex * Process.pointerSize).readPointer();
    const info = methodFromName(classFromType(type), Memory.allocUtf8String(methodName), argc);
    if (info.isNull()) throw new Error('MethodInfo was null');
    return info.readPointer();
  } finally { detachThread(token); }
}

const method = resolveMethod(MPD_TYPE_INDEX, 'DQQW', 2);
const mppSpawnMethod = resolveMethod(MPP_TYPE_INDEX, 'SMND', 3);
const mppCostCurrent = resolveMethod(MPP_TYPE_INDEX, 'SMBR', 0);
const mppCostNext = resolveMethod(MPP_TYPE_INDEX, 'SMBT', 0);
let calibrationArmed = false, calibratedThis = null, forcedValue = null;
let callsSeen = 0, replacements = 0;
const seenInstances = new Set();
let calibrationIgnore = new Set();
let learnArmed = false;
let mergeDiscovery = false, mergeCallerRva = null, mergeForcedValue = null;
const mergeCandidates = new Map();
let mergeReplacements = 0;
const activeMppByThread = new Map();
const lastMppByThread = new Map();
let calibratedMpp = null, noSummonCost = false, costReplacements = 0;

Interceptor.attach(mppSpawnMethod, {
  onEnter(args) {
    this.tid = Process.getCurrentThreadId();
    const stack = activeMppByThread.get(this.tid) || [];
    stack.push(args[0]);
    activeMppByThread.set(this.tid, stack);
    lastMppByThread.set(this.tid, args[0]);
  },
  onLeave(retval) {
    const stack = activeMppByThread.get(this.tid) || [];
    stack.pop();
    if (stack.length === 0) activeMppByThread.delete(this.tid);
    else activeMppByThread.set(this.tid, stack);
  }
});

function hookCost(address, label) {
  Interceptor.attach(address, {
    onEnter(args) { this.matches = calibratedMpp !== null && args[0].equals(calibratedMpp); },
    onLeave(retval) {
      if (!noSummonCost || !this.matches) return;
      const original = retval.toInt32();
      retval.replace(ptr(0)); costReplacements++;
      if (costReplacements <= 10 || costReplacements % 100 === 0)
        send({event:'cost_forced', method:label, originalCost:original, forcedCost:0,
              replacements:costReplacements});
    }
  });
}
hookCost(mppCostCurrent, 'SMBR');
hookCost(mppCostNext, 'SMBT');

Interceptor.attach(method, {
  onEnter(args) {
    this.instance = args[0];
    const tid = Process.getCurrentThreadId();
    const stack = activeMppByThread.get(tid) || [];
    this.mpp = stack.length ? stack[stack.length - 1] : (lastMppByThread.get(tid) || null);
    this.callerRva = this.returnAddress.sub(ga.base);
    this.inSummonPath = this.callerRva.equals(EXPECTED_CALLER_RVA);
  },
  onLeave(retval) {
    const original = retval.toInt32();
    const instanceKey = this.instance.toString();
    if (!this.inSummonPath) {
      if (calibratedThis === null || !this.instance.equals(calibratedThis)) return;
      const callerKey = this.callerRva.toString();
      if (mergeDiscovery) {
        const count = (mergeCandidates.get(callerKey) || 0) + 1;
        mergeCandidates.set(callerKey, count);
        send({event:'merge_candidate', callerRva:callerKey, count, result:original});
        if (count >= 3) {
          mergeCallerRva = this.callerRva;
          mergeDiscovery = false;
          send({event:'merge_discovered', callerRva:callerKey, confirmations:count});
        }
      }
      if (mergeForcedValue !== null && mergeCallerRva !== null && this.callerRva.equals(mergeCallerRva)) {
        retval.replace(ptr(mergeForcedValue >>> 0));
        mergeReplacements++;
        send({event:'merge_forced', callerRva:callerKey, originalResult:original,
              forcedResult:mergeForcedValue, replacements:mergeReplacements});
      }
      return;
    }
    callsSeen++;
    const wasSeenBefore = seenInstances.has(instanceKey);
    seenInstances.add(instanceKey);
    if (calibrationArmed && !calibrationIgnore.has(instanceKey)) {
      calibratedThis = this.instance;
      if (this.mpp !== null) calibratedMpp = this.mpp;
      calibrationArmed = false;
      send({event:'calibrated', instance:calibratedThis.toString(),
            mpp:calibratedMpp === null ? null : calibratedMpp.toString(), observedResult:original});
      return;
    }
    if (learnArmed && calibratedThis !== null && this.instance.equals(calibratedThis)) {
      learnArmed = false;
      send({event:'learned', instance:instanceKey, observedResult:original});
      return;
    }
    if (forcedValue !== null && calibratedThis !== null && this.instance.equals(calibratedThis)) {
      retval.replace(ptr(forcedValue >>> 0));
      replacements++;
      send({event:'forced', instance:this.instance.toString(), originalResult:original,
            forcedResult:forcedValue, replacements:replacements});
    } else {
      send({event:'observed', instance:instanceKey, result:original, wasSeenBefore});
    }
  }
});

rpc.exports = {
  armcalibration() {
    calibrationIgnore = new Set(seenInstances);
    calibrationArmed = true;
    return {armed:true, ignoredExistingInstances:Array.from(calibrationIgnore)};
  },
  setforced(value) {
    const parsed = Number(value);
    if (!Number.isInteger(parsed) || parsed < -2147483648 || parsed > 4294967295)
      throw new Error('Result must fit in 32 bits');
    forcedValue = parsed | 0;
    return {forcedResult:forcedValue};
  },
  disable() { forcedValue = null; return {forcedResult:null}; },
  startmergediscovery() {
    if (calibratedThis === null) throw new Error('Calibrate the local player first');
    mergeCandidates.clear(); mergeCallerRva = null; mergeForcedValue = null; mergeDiscovery = true;
    return {mergeDiscovery:true, requiredConfirmations:3};
  },
  setmergeforced(value) {
    if (mergeCallerRva === null) throw new Error('Discover the merge callsite first');
    const parsed = Number(value);
    if (!Number.isInteger(parsed) || parsed < -2147483648 || parsed > 4294967295)
      throw new Error('Result must fit in 32 bits');
    mergeForcedValue = parsed | 0;
    return {mergeForcedResult:mergeForcedValue, mergeCallerRva:mergeCallerRva.toString()};
  },
  disablemerge() { mergeForcedValue = null; return {mergeForcedResult:null}; },
  setnocost(enabled) {
    if (!!enabled && calibratedMpp === null) throw new Error('Calibrate with one local summon first');
    noSummonCost = !!enabled;
    return {noSummonCost, calibratedMpp:calibratedMpp.toString()};
  },
  armlearn() {
    if (calibratedThis === null) throw new Error('Calibrate the local player first');
    forcedValue = null;
    learnArmed = true;
    return {learning:true};
  },
  clearcalibration() {
    calibrationArmed = false; calibratedThis = null; forcedValue = null; learnArmed = false;
    mergeDiscovery = false; mergeCallerRva = null; mergeForcedValue = null; mergeCandidates.clear();
    calibratedMpp = null; noSummonCost = false;
    return {cleared:true};
  },
  status() {
    return {method:method.toString(), callerRva:EXPECTED_CALLER_RVA.toString(),
      calibrationArmed, learnArmed, calibratedInstance:calibratedThis === null ? null : calibratedThis.toString(),
      forcedResult:forcedValue, callsSeen, replacements,
      mergeDiscovery, mergeCallerRva:mergeCallerRva === null ? null : mergeCallerRva.toString(),
      mergeForcedResult:mergeForcedValue, mergeReplacements,
      calibratedMpp:calibratedMpp === null ? null : calibratedMpp.toString(),
      noSummonCost, costReplacements,
      seenInstances:Array.from(seenInstances), ignoredInstances:Array.from(calibrationIgnore)};
  }
};
send({event:'ready', method:method.toString(), callerRva:EXPECTED_CALLER_RVA.toString(),
      mode:'observe-only until calibrated and force is enabled'});
