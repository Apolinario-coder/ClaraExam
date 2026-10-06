//! Temporary shortcut filtering. No keystrokes are recorded or sent anywhere.
use pyo3::prelude::*;
use std::cell::RefCell;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Arc};
use std::thread::{self, JoinHandle};
use std::time::Duration;
use windows_sys::Win32::Foundation::{GetLastError, LPARAM, LRESULT, WPARAM};
use windows_sys::Win32::System::Threading::GetCurrentThreadId;
use windows_sys::Win32::UI::Input::KeyboardAndMouse::*;
use windows_sys::Win32::UI::WindowsAndMessaging::*;

static GUARD_INSTALLED: AtomicBool = AtomicBool::new(false);
thread_local! { static KEYS: RefCell<KeyState> = RefCell::new(KeyState::new()); }

#[pyfunction]
pub fn shortcut_blocked(key: u16, alt: bool, ctrl: bool, shift: bool) -> bool {
    if matches!(key, VK_LWIN | VK_RWIN | VK_F5 | VK_F11 | VK_F12 | VK_SNAPSHOT | VK_APPS) {
        return true;
    }
    if alt && matches!(key, VK_TAB | VK_ESCAPE | VK_F4 | VK_SPACE) { return true; }
    if ctrl && matches!(key, VK_ESCAPE | VK_F4) { return true; }
    // Preserve AltGr combinations, typing, clipboard shortcuts and Tab navigation.
    if ctrl && !alt {
        if [VK_L, VK_N, VK_O, VK_P, VK_R, VK_S, VK_T, VK_U, VK_W].contains(&key) { return true; }
        if shift && [VK_I, VK_J, VK_C, VK_K].contains(&key) { return true; }
    }
    false
}

struct KeyState { pressed: [bool; 256], suppressed: [bool; 256] }
impl KeyState {
    fn new() -> Self { Self { pressed: [false; 256], suppressed: [false; 256] } }
    fn group(&self, keys: &[u16]) -> bool { keys.iter().any(|k| self.pressed[*k as usize]) }

    fn process(&mut self, key: u16, down: bool, alt_flag: bool) -> bool {
        let index = key as usize;
        if index >= self.pressed.len() { return false; }
        self.pressed[index] = down;
        // Pair a swallowed keydown with its keyup even if Alt/Ctrl was released first.
        if !down {
            let blocked = self.suppressed[index];
            self.suppressed[index] = false;
            return blocked;
        }
        let alt = alt_flag || self.group(&[VK_MENU, VK_LMENU, VK_RMENU]);
        let ctrl = self.group(&[VK_CONTROL, VK_LCONTROL, VK_RCONTROL]);
        let shift = self.group(&[VK_SHIFT, VK_LSHIFT, VK_RSHIFT]);
        let blocked = self.suppressed[index] || shortcut_blocked(key, alt, ctrl, shift);
        self.suppressed[index] = blocked;
        blocked
    }

    fn seed_held_modifiers(&mut self) {
        // Outside the callback: async state isn't updated for the current hook event.
        for key in [VK_LMENU, VK_RMENU, VK_LCONTROL, VK_RCONTROL, VK_LSHIFT, VK_RSHIFT] {
            self.pressed[key as usize] = unsafe { GetAsyncKeyState(key as i32) } < 0;
        }
    }
}

unsafe extern "system" fn keyboard_callback(code: i32, message: WPARAM, data: LPARAM) -> LRESULT {
    if code == HC_ACTION as i32 && data != 0 {
        let down = message == WM_KEYDOWN as usize || message == WM_SYSKEYDOWN as usize;
        let up = message == WM_KEYUP as usize || message == WM_SYSKEYUP as usize;
        if down || up {
            let info = unsafe { &*(data as *const KBDLLHOOKSTRUCT) };
            let blocked = KEYS.with(|keys| keys.borrow_mut().process(
                info.vkCode as u16, down, info.flags & LLKHF_ALTDOWN != 0));
            if blocked { return 1; }
        }
    }
    unsafe { CallNextHookEx(std::ptr::null_mut(), code, message, data) }
}

struct InstalledSlot;
impl Drop for InstalledSlot {
    fn drop(&mut self) { GUARD_INSTALLED.store(false, Ordering::Release); }
}
struct NativeHook(HHOOK);
impl Drop for NativeHook {
    fn drop(&mut self) { unsafe { UnhookWindowsHookEx(self.0); } }
}

#[pyclass]
pub struct KeyboardGuard {
    thread_id: u32,
    thread: Option<JoinHandle<()>>,
    running: Arc<AtomicBool>,
    cancel: Arc<AtomicBool>,
}

#[pymethods]
impl KeyboardGuard {
    /// Installed thread status; Windows can still remove a timed-out hook silently.
    #[getter]
    fn active(&self) -> bool { self.running.load(Ordering::Acquire) }

    fn stop(&mut self) {
        if let Some(handle) = self.thread.take() {
            self.cancel.store(true, Ordering::Release);
            unsafe { PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0); }
            // The pump checks cancellation every 50 ms even if posting fails.
            let _ = handle.join();
        }
    }
}
impl Drop for KeyboardGuard { fn drop(&mut self) { self.stop(); } }

#[pyfunction]
pub fn start_keyboard_guard() -> PyResult<KeyboardGuard> {
    if GUARD_INSTALLED.compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire).is_err() {
        return Err(pyo3::exceptions::PyRuntimeError::new_err("O bloqueio do teclado já está ativo."));
    }
    let running = Arc::new(AtomicBool::new(false));
    let state = running.clone();
    let cancel = Arc::new(AtomicBool::new(false));
    let abort = cancel.clone();
    let (ready_tx, ready_rx) = mpsc::sync_channel(1);
    let handle = thread::Builder::new().name("clara-keyboard".into()).spawn(move || {
        let _slot = InstalledSlot;
        let thread_id = unsafe { GetCurrentThreadId() };
        let mut message = unsafe { std::mem::zeroed::<MSG>() };
        unsafe { PeekMessageW(&mut message, std::ptr::null_mut(), 0, 0, PM_NOREMOVE); }
        if abort.load(Ordering::Acquire) { return; }
        KEYS.with(|keys| keys.borrow_mut().seed_held_modifiers());
        let hook = unsafe { SetWindowsHookExW(WH_KEYBOARD_LL, Some(keyboard_callback), std::ptr::null_mut(), 0) };
        if hook.is_null() {
            let error = unsafe { GetLastError() };
            let _ = ready_tx.send(Err(error));
            return;
        }
        let _hook = NativeHook(hook);
        if abort.load(Ordering::Acquire) { return; }
        state.store(true, Ordering::Release);
        if ready_tx.send(Ok(thread_id)).is_ok() {
            'pump: while !abort.load(Ordering::Acquire) {
                unsafe { MsgWaitForMultipleObjects(0, std::ptr::null(), 0, 50, QS_ALLINPUT); }
                while unsafe { PeekMessageW(&mut message, std::ptr::null_mut(), 0, 0, PM_REMOVE) } != 0 {
                    if message.message == WM_QUIT || abort.load(Ordering::Acquire) { break 'pump; }
                    unsafe { TranslateMessage(&message); DispatchMessageW(&message); }
                }
            }
        }
        // RAII unhooks before releasing the process-wide installation slot.
        state.store(false, Ordering::Release);
    }).map_err(|error| {
        GUARD_INSTALLED.store(false, Ordering::Release);
        pyo3::exceptions::PyRuntimeError::new_err(format!("Falha ao iniciar bloqueio de atalhos: {error}"))
    })?;
    match ready_rx.recv_timeout(Duration::from_secs(3)) {
        Ok(Ok(thread_id)) => Ok(KeyboardGuard { thread_id, thread: Some(handle), running, cancel }),
        Ok(Err(code)) => {
            let _ = handle.join();
            Err(pyo3::exceptions::PyRuntimeError::new_err(format!("Não foi possível ativar o bloqueio de atalhos do Windows (erro {code}).")))
        }
        Err(_) => {
            // A late setup sees cancellation; a late installed hook exits its pump.
            cancel.store(true, Ordering::Release);
            if handle.is_finished() { let _ = handle.join(); }
            Err(pyo3::exceptions::PyRuntimeError::new_err("O bloqueio de atalhos do Windows não respondeu."))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn system_and_browser_shortcuts() {
        for key in [VK_F11, VK_F12, VK_LWIN, VK_RWIN, VK_SNAPSHOT] {
            assert!(shortcut_blocked(key, false, false, false));
        }
        for key in [VK_TAB, VK_ESCAPE, VK_F4, VK_SPACE] {
            assert!(shortcut_blocked(key, true, false, false));
        }
        for key in [VK_I, VK_J, VK_C, VK_K] {
            assert!(shortcut_blocked(key, false, true, true));
        }
        assert!(shortcut_blocked(VK_ESCAPE, false, true, true));
        assert!(shortcut_blocked(VK_U, false, true, false));
    }
    #[test]
    fn regular_input_and_altgr_are_preserved() {
        for key in [VK_A, VK_TAB, VK_ESCAPE, VK_SPACE, VK_RETURN] {
            assert!(!shortcut_blocked(key, false, false, false));
        }
        for key in [VK_C, VK_V, VK_X, VK_A, VK_Z] {
            assert!(!shortcut_blocked(key, false, true, false));
        }
        assert!(!shortcut_blocked(VK_S, true, true, false));
        assert!(!shortcut_blocked(VK_DELETE, true, true, false));
    }
    #[test]
    fn both_modifier_sides_and_key_releases() {
        let mut keys = KeyState::new();
        keys.process(VK_LMENU, true, false);
        keys.process(VK_RMENU, true, false);
        keys.process(VK_LMENU, false, false);
        assert!(keys.process(VK_TAB, true, false));
        keys.process(VK_RMENU, false, false);
        assert!(keys.process(VK_TAB, false, false));
        assert!(!keys.process(VK_TAB, true, false));
        assert!(!keys.process(VK_TAB, false, false));
        assert!(keys.process(VK_TAB, true, true));
    }
}
