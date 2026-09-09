# Legend

**Figure Sx. Cutoff sensitivity in the overall test set, across clinical domains, and across broad review types.**

Panel A shows the overall 24-SR test set. Panels B-F show test-set performance stratified by clinical domain, and Panels G-J show performance stratified by broad review type. Each point represents cutoff 0, 30, 50, 60, 70, 80, or 90. Colored lines show Claude, Codex, and Gemini separately; the black line shows the unweighted mean of the three LLM-specific estimates. Recall is the mean recall across systematic reviews in the stratum. NNR is the ordinary manuscript metric: the mean per-SLR number needed to read, calculated as retained hits divided by true-positive hits within each SLR and then averaged.

Because NNR is averaged per review, it is not mathematically forced to decrease at every stricter cutoff. NNR can increase if a cutoff removes true positives disproportionately in one or more reviews, even though retained hit counts decrease. Domain- and broad review type-specific findings are descriptive because each subgroup contained few reviews, and broad review type was assigned post hoc for robustness assessment rather than for rulebook generation, refinement, or cutoff selection.
