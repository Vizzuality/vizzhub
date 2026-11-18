import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { useFocusOnMount } from '../useFocusOnMount';

function Editor(): JSX.Element {
  const focusOnMount = useFocusOnMount<HTMLInputElement>();
  return <input aria-label="editor" ref={focusOnMount} />;
}

describe('useFocusOnMount', () => {
  it('focuses the element when it mounts', () => {
    render(<Editor />);
    expect(screen.getByLabelText('editor')).toHaveFocus();
  });
});
