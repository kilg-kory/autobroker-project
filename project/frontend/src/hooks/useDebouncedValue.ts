import { useEffect, useState } from 'react';

/**
 * Отдаёт значение, только когда оно не менялось `delay` миллисекунд.
 *
 * Нужно для быстрых переключателей: клики по галочкам не должны превращаться
 * в запрос на каждый клик — на сервере такой запрос стоит сотни миллисекунд.
 */
export function useDebouncedValue<T>(value: T, delay = 400): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
