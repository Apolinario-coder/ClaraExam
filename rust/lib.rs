use pyo3::prelude::*;
use url::Url;
mod keyboard;

fn origin(input: &str) -> Option<String> {
    if input.chars().any(|c| c.is_control() || c == '\\') {
        return None;
    }
    let parsed = Url::parse(input).ok()?;
    if parsed.scheme() != "https" || parsed.host_str().is_none()
        || !parsed.username().is_empty() || parsed.password().is_some() {
        return None;
    }
    Some(parsed.origin().ascii_serialization())
}

#[pyfunction]
fn https_origin(input: &str) -> PyResult<String> {
    origin(input).ok_or_else(|| pyo3::exceptions::PyValueError::new_err(
        "Use um endereço HTTPS válido, sem usuário ou senha na URL."))
}

#[pyfunction]
fn is_allowed(input: &str, allowed_origins: Vec<String>) -> bool {
    let Some(candidate) = origin(input) else { return false; };
    allowed_origins.iter().filter_map(|entry| origin(entry))
        .any(|allowed| candidate == allowed)
}

#[pymodule]
fn _core(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(https_origin, module)?)?;
    module.add_function(wrap_pyfunction!(is_allowed, module)?)?;
    module.add_class::<keyboard::KeyboardGuard>()?;
    module.add_function(wrap_pyfunction!(keyboard::start_keyboard_guard, module)?)?;
    module.add_function(wrap_pyfunction!(keyboard::shortcut_blocked, module)?)?;
    Ok(())
}
